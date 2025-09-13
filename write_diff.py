import os
import subprocess
import shutil
import hashlib
import myers
import sys
import json
import time

def is_text_file(file_path):
    # mime = magic.from_file(file_path, mime=True)
    # return mime.startswith("text/")
    return file_path.endswith(".py") or file_path.endswith(".js") or file_path.endswith(".m")
def get_file_hash(file_path, hash_algorithm='sha256'):
    """Calculate the hash value of a file"""
    hash_func = hashlib.new(hash_algorithm)  # Use the specified hash algorithm
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):  # Read the file in chunks
            hash_func.update(chunk)
    return hash_func.hexdigest()

def compare_files(file1, file2, hash_algorithm='sha256'):
    """Compare if two files are the same"""
    hash1 = get_file_hash(file1, hash_algorithm)
    hash2 = get_file_hash(file2, hash_algorithm)
    return hash1 == hash2

def is_zero(n: int) -> bool:
    return (n & 0x3F) == 0x3F

def is_too_small(file_path, size = 48):
    return os.path.getsize(file_path) <= size

def copy_file_or_folder(src, dest):
    """Copy file or folder from source to destination."""
    if os.path.isdir(src):  # If it's a folder, copy the entire directory
        shutil.copytree(src, dest)
        # print(f"Folder copied: {src} -> {dest}")
    elif os.path.isfile(src):  # If it's a file, copy the single file
        shutil.copy2(src, dest)
        # print(f"File copied: {src} -> {dest}")
    else:
        print(f"Path {src} is neither a file nor a directory.")

def get_top_layer(image_path, image_dir = "image_unzip"):
    # unpack image
    subprocess.run(['tar', '-xf', image_path , '-C',image_dir])

    # read index.json and get manifest path
    index_handle = open(image_dir + '/index.json', 'r+')
    index_data = json.load(index_handle)
    manifests_digest = index_data['manifests'][0]['digest']
    manifest_path = image_dir + f"/blobs/sha256/{manifests_digest[7:]}"  # delete prefix "sha256:"
    print(f"Manifests digest from index.json, path is: {manifest_path}")


    # extact top layer's digest
    manifest_handle = open(manifest_path, 'r+')
    manifest_data = json.load(manifest_handle)
    top_layer_hash = manifest_data['layers'][-1]['digest'][7:]
    config_hash = manifest_data['config']['digest'][7:]

    # move top layer
    copy_file_or_folder(image_dir + '/blobs/sha256/' + top_layer_hash, "diff_content/" + top_layer_hash)

    
def get_chunks_break(file_path, base = 256, window_size = 48, prime = 2**63 - 25):
    num_of_breakpoints = 0
    chunks_end = []
    highest = base ** (window_size - 1) % prime
    with open(file_path, 'rb') as f:
        byte_list = f.read()
    if is_too_small(file_path):
        chunks_end.append(len(byte_list) - 1)
        return chunks_end
    current_hash = 0
    for i in range(window_size):
        current_hash = (current_hash * base + byte_list[i]) % prime
    if(is_zero(current_hash)):
        chunks_end.append(window_size - 1)
        num_of_breakpoints += 1
    for i in range(1, len(byte_list) - window_size + 1):
        current_hash = (base * (current_hash - byte_list[i - 1] * highest) + byte_list[i + window_size - 1]) % prime
        if(is_zero(current_hash)):
            chunks_end.append(i + window_size - 1)
            num_of_breakpoints += 1
    if num_of_breakpoints == 0 or len(byte_list) - 1 > chunks_end[-1]:
        chunks_end.append(len(byte_list) - 1)
        num_of_breakpoints += 1
    if(num_of_breakpoints == len(byte_list) - window_size + 1):
        return [len(byte_list) - 1]
    return chunks_end

def edit_path_to_str(edit_path):
    # Convert the edit path to string
    edit_path_str = ''
    for i in range(len(edit_path)):
        if edit_path[i][0] == 'R':
            edit_path_str += f'R {edit_path[i][1]} '
        elif edit_path[i][0] == 'D':
            edit_path_str += f'D {edit_path[i][1]} '
        elif edit_path[i][0] == 'I':
            edit_path_str += f'I {edit_path[i][1]} '
    return edit_path_str

def extract_diff(extracted_file, target_file, edit_path, is_text = True):
    if is_text:
        with open(extracted_file, 'r') as file:
            extracted_lines = file.readlines()
    else:
        with open(extracted_file, 'rb') as file:
            extracted_lines = file.read()
    write_way = 'w' if is_text else 'wb'
    with open(target_file, write_way) as file:
        cur_line_location = 0
        for i in range(len(edit_path)):
            if edit_path[i][0] == 'R':
                cur_line_location += edit_path[i][1]
            elif edit_path[i][0] == 'I':
                if is_text:
                    file.writelines(extracted_lines[cur_line_location:cur_line_location + edit_path[i][1]])
                else:
                    file.write(extracted_lines[cur_line_location:cur_line_location + edit_path[i][1]])
                cur_line_location += edit_path[i][1]

sub_time = 0
back_start = time.time()
def write_diff(source, dest, path_prefix = '', target = 'diff_content', target_file_handle = None, write_way = 'inc'):
    is_root_call = target_file_handle is None
    if is_root_call:
        target_file_handle = open(f"{target}/diff.txt", "w")

    source_list = os.listdir(source)
    dest_list   = os.listdir(dest)

    added_list   = sorted(list(set(dest_list) - set(source_list)))
    removed_list = sorted(list(set(source_list) - set(dest_list)))
    common_list  = sorted(list(set(source_list) & set(dest_list)))

    for item in removed_list:
        source_path = os.path.join(source, item)
        if os.path.isfile(source_path):
            target_file_handle.write(f'-f {path_prefix + item}\n')
        elif os.path.isdir(source_path):
            target_file_handle.write(f'-d {path_prefix + item}\n')

    for item in added_list:
        dest_path = os.path.join(dest, item)
        if os.path.isfile(dest_path):
            target_file_handle.write(f'+f {path_prefix + item}\n')
            copy_file_or_folder(dest_path, f"{target}/{path_prefix + item}")
            print("+f: ", path_prefix + item)
        elif os.path.isdir(dest_path):
            target_file_handle.write(f'+d {path_prefix + item}\n')
            copy_file_or_folder(dest_path, f"{target}/{path_prefix + item}")
            print("+d: ", path_prefix + item)

    for item in common_list:
        source_path = os.path.join(source, item)
        dest_path = os.path.join(dest, item)
        if os.path.isfile(source_path) and not compare_files(source_path, dest_path):
            if write_way == 'all':
                target_file_handle.write(f'~ {path_prefix + item}\n')
                copy_file_or_folder(dest_path, f"{target}/{path_prefix + item}")
            elif write_way == 'inc':
                if is_text_file(dest_path):
                    m_start = time.time()
                    edit_path = myers.text_get_diff(source_path, dest_path)
                    m_time = time.time() - m_start
                    global sub_time
                    sub_time += m_time
                    if len(edit_path) <= 2:
                        target_file_handle.write(f'~ {path_prefix + item}\n')
                        copy_file_or_folder(dest_path, f"{target}/{path_prefix + item}")
                        print("~text:all", f"{target}/{path_prefix + item}")
                    else:
                        edit_str = edit_path_to_str(edit_path)
                        log_line = f"~t {path_prefix + item} {edit_str[:-1]}\n"
                        target_file_handle.write(log_line)
                        extract_diff(dest_path, f"{target}/{path_prefix + item}", edit_path, is_text = True)
                        print("~text:inc", f"{target}/{path_prefix + item}")
                else:
                    source_end, dest_end = get_chunks_break(source_path), get_chunks_break(dest_path)
                    print("len(source_chunks_length)", len(source_end), "dest_chunks_length", len(dest_end))
                    edit_path = myers.binary_get_diff(source_path, dest_path, source_end, dest_end)
                    if len(edit_path) <= 2:
                        target_file_handle.write(f'~ {path_prefix + item}\n')
                        copy_file_or_folder(dest_path, f"{target}/{path_prefix + item}")
                        print("~binary:no common chunks", f"{target}/{path_prefix + item}")
                    else:
                        edit_str = edit_path_to_str(edit_path)
                        log_line = f"~b {path_prefix + item} {edit_str[:-1]}\n"
                        target_file_handle.write(log_line)
                        extract_diff(dest_path, f"{target}/{path_prefix + item}", edit_path, is_text = False)
                        print("~binary:inc", f"{target}/{path_prefix + item}")
        elif os.path.isdir(dest_path):
            os.makedirs(f"{target}/{path_prefix + item}", exist_ok=True)
            write_diff(source_path, dest_path, path_prefix = path_prefix + item + '/', target_file_handle = target_file_handle, write_way = write_way)

    if is_root_call:
        target_file_handle.close()

if __name__ == "__main__":
    write_way = sys.argv[1] # 'all' or 'inc' or 'layer'
    # To create or clean diff_content
    diff_content = 'diff_content'
    image_unzip = 'image_unzip'
    subprocess.run(['rm', '-rf', diff_content])
    subprocess.run(['rm', '-rf', image_unzip])
    os.makedirs(diff_content)
    os.makedirs(image_unzip)
    if write_way == 'layer':
        get_top_layer('workspace/ctestappoci.tar', 'image_unzip')
    else:
        write_diff('/home/breeze/yolov3/before_yolo', '/home/breeze/yolov3/1changed8', write_way = write_way)
    if os.path.exists('workspace/diff_content.tar.gz'):
        os.remove('workspace/diff_content.tar.gz')
    subprocess.run(['tar', '-czf', 'workspace/diff_content.tar.gz', 'diff_content'])
    back_time = time.time() - back_start - sub_time
    print(back_time * 1000)
    print("Extraction complete.")
