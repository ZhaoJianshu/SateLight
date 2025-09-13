import os
import hashlib
import myers
import write_diff


def hash_file(filepath, algo='sha256'):
    h = hashlib.new(algo)
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()

def get_all_files(directory):
    file_map = {}
    for root, _, files in os.walk(directory):
        for file in files:
            abs_path = os.path.join(root, file)
            rel_path = os.path.relpath(abs_path, directory)
            file_map[rel_path] = abs_path
    return file_map

def lines_byte_lengths(file_path):
    length = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            length.append(len(line.encode('utf-8')))
    return length

def chunks_byte_lengths(end_of_chunks):
    length = []
    prev_end = -1
    for i in range(0, len(end_of_chunks)):
        length.append(end_of_chunks[i] - prev_end)
        prev_end = end_of_chunks[i]
    return length

def get_inserted_bytes(edit_path, length = []):
    bytes_of_inserted = 0
    y = 0
    for item in edit_path:
        if item[0] == 'R':
            y += item[1]
        elif item[0] == 'I':
            if not length:
                bytes_of_inserted += item[1]
            else:
                for i in range(item[1]):
                    bytes_of_inserted += length[y + i]
                y += item[1]
    return bytes_of_inserted

def get_rate_of_change_of_dirs(dir1, dir2):
    global nums_of_new_dict_bytes, nums_of_inserted_bytes
    files1 = get_all_files(dir1)
    files2 = get_all_files(dir2)

    all_keys = set(files1.keys()).union(set(files2.keys()))

    for key in sorted(all_keys):
        path1 = files1.get(key)
        path2 = files2.get(key)

        if not path1 and path2:
            nums_of_new_dict_bytes += os.path.getsize(path2)
            print(f"Only in new dict:{path2}", os.path.getsize(path2))
        elif path1 and path2:
            equal = hash_file(path1) == hash_file(path2)
            is_text = write_diff.is_text_file(path2)
            if equal:
                nums_of_new_dict_bytes += os.path.getsize(path2)
                print(f"The same file{path2}:", os.path.getsize(path2))
            elif is_text:
                edit_path = myers.text_get_diff(path1, path2)
                length = lines_byte_lengths(path2)
                inserted_bytes = get_inserted_bytes(edit_path, length)
                nums_of_inserted_bytes += inserted_bytes
                nums_of_new_dict_bytes += os.path.getsize(path2)
                print(f"The different files{path2}:", inserted_bytes, os.path.getsize(path2))
            else:
                end_of_file1 = write_diff.get_chunks_break(path1)
                end_of_file2 = write_diff.get_chunks_break(path2)
                print("len(origin_chunks)", len(end_of_file1))
                print("len(updated_chunks)", len(end_of_file2))
                edit_path = myers.binary_get_diff(path1, path2, end_of_file1, end_of_file2)
                inserted_bytes = get_inserted_bytes(edit_path = edit_path)
                nums_of_inserted_bytes += inserted_bytes
                nums_of_new_dict_bytes += os.path.getsize(path2)
    print("change rate of dict:",  nums_of_inserted_bytes / nums_of_new_dict_bytes)
                        




nums_of_new_dict_bytes = 0
nums_of_inserted_bytes = 0
if __name__ == "__main__":
    # print(lines_byte_lengths("/home/breeze/diff/compare.py"))
    # get_rate_of_change_of_dirs('/home/breeze/test/1', '/home/breeze/test/2')
    # get_rate_of_change_of_dirs('/home/breeze/yolov3/before_yolo', '/home/breeze/yolov3/2changed2')
    # get_rate_of_change_of_dirs('/home/breeze/yolo/before_yolo', '/home/breeze/yolo/0changed8')
    get_rate_of_change_of_dirs('/home/breeze/yolo/before_yolo/', '/home/breeze/yolo/1/')


