import os
import json
import subprocess
import shutil
import hashlib
import gzip
import sys
import time
import stat

staged_layer = "workspace/tmp/staged_layer"
image_dir = "workspace/tmp/extract_dir"
workspace = "workspace"
backup_dir = "workspace/backup"
image_name = "testapp"
diff_content = 'workspace/tmp/staged_diff_content/diff_content'
staged_diff_content = 'workspace/tmp/staged_diff_content'

diff_id_list = [0, 1]

def get_sha256(filename):
    sha256_hash = hashlib.sha256()
    with open(filename, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def get_gzip_layer_diff_id(gzip_filename):
    """Calculate the SHA256 (i.e., diff_id) of the file after decompressing the gzip compression layer"""
    diff_id_hash = hashlib.sha256()
    with gzip.open(gzip_filename, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            diff_id_hash.update(chunk)
    return f"{diff_id_hash.hexdigest()}"

def get_diff_id_of_tar(tar_filename):
    return subprocess.run(['sha256sum', tar_filename], capture_output=True, text=True).stdout.split()[0]

def oci_to_docker(oci_image, docker_image, tag = 'latest'):
    subprocess.run(['skopeo', 'copy', 'oci-archive:workspace/' + oci_image, f'docker-archive:workspace/{docker_image}:{image_name}:{tag}'])
    
def remove_dir_children(dir_path_list):
    for dir_path in dir_path_list:
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)
            os.makedirs(dir_path, exist_ok=True)
            
def remove_file_or_dir(path_list):
    for path in path_list:
        if os.path.isfile(path):
            os.remove(path)
        elif os.path.isdir(path):
            shutil.rmtree(path)

def back_up_layer(top_layer_hash):
    app_backup = backup_dir + '/' + image_name
    os.makedirs(app_backup)
    os.rename(image_dir + f"/blobs/sha256/" + top_layer_hash, app_backup + '/' + top_layer_hash)
    
def back_up_changed_file_line(diff_file):
    with open(diff_file, 'r') as f:
        lines = f.readlines()
    for line in lines:
        if line.startswith('~'):
            line.strip()
            change_list = line.split(" ")
            file_name = change_list[1]
            file_path = staged_layer + '/app/' + file_name
            with open(file_path, 'r') as file:
                updated_lines = file.readlines()
            with open(f"{backup_dir}/{image_name}/diff_content/{file_name}", 'w') as file:
                cur_line_location = 0 # location of line to be copied
                for i in range(2, len(change_list), 2):
                    if change_list[i] == 'R':
                        cur_line_location += int(change_list[i + 1])
                    elif change_list[i] == 'I':
                        for j in range(cur_line_location, cur_line_location + int(change_list[i + 1])):
                            file.write(updated_lines[j])
                        cur_line_location += int(change_list[i + 1])
            new_file_name = f"{backup_dir}/{image_name}/diff_content/{file_name}"
            st = os.stat(new_file_name)
            os.chmod(new_file_name, st.st_mode | stat.S_IEXEC)


def invert_diff_file(diff_file, target_path, invert_change_path = False): # invert_way: 'all' or 'inc'
    with open(diff_file, 'r') as f:
        lines = f.readlines()
    with open(target_path, 'w') as f:
        for line in lines:
            if line.startswith('+'):
                f.write('-' + line[1:])
            elif line.startswith('-'):
                f.write('+' + line[1:])
            elif line.startswith('~'):
                if invert_change_path:
                    first_pos = line.find(' ')
                    second_pos = line.find(' ', first_pos + 1)
                    new_line = line[:second_pos]
                    for char in line[second_pos:]:
                        if char == 'I':
                            new_line += 'D'
                        elif char == 'D':
                            new_line += 'I'
                        else:
                            new_line += char
                    f.write(new_line)
                else:
                    f.write(line)
            else:
                f.write(line)


def restore_with_layer(original_image, restored_image, backup_layer_hash):
    # unpack image of specfic filename
    subprocess.run(['tar', '-xf', original_image , '-C', image_dir])

    # read index.json and get manifest path
    index_handle = open(image_dir + '/index.json', 'r+')
    index_data = json.load(index_handle)
    manifests_digest = index_data['manifests'][0]['digest']
    manifest_path = image_dir + f"/blobs/sha256/{manifests_digest[7:]}"  # delete prefix "sha256:"

    # extact top layer's digest
    manifest_handle = open(manifest_path, 'r+')
    manifest_data = json.load(manifest_handle)
    top_layer_hash = manifest_data['layers'][-1]['digest'][7:]
    config_hash = manifest_data['config']['digest'][7:]

    # restore top layer
    os.remove(image_dir + "/blobs/sha256/" + top_layer_hash)
    os.rename(f"{backup_dir}/{image_name}/{backup_layer_hash}", f"{image_dir}/blobs/sha256/{backup_layer_hash}")

    new_layer_hash = backup_layer_hash
    new_layer_diff_id = get_gzip_layer_diff_id(f"{image_dir}/blobs/sha256/{backup_layer_hash}")
    diff_id_list[1] = new_layer_diff_id
    print(f"new layer_diff_id: {new_layer_diff_id}")

    # Write config: substitute top layer diff_id
    config_path = image_dir + '/blobs/sha256/' + config_hash
    with open(config_path, 'r+', encoding = 'utf-8') as config_handle:
        config_data = json.load(config_handle)
        config_data['rootfs']['diff_ids'][-1] = "sha256:" + new_layer_diff_id
        config_handle.seek(0)
        json.dump(config_data, config_handle, ensure_ascii=False)
        config_handle.truncate()
    new_config_hash = get_sha256(config_path)
    os.rename(config_path, image_dir + '/blobs/sha256/' + new_config_hash)
    print(f"config_hash: {config_hash} -> new_config_hash: {new_config_hash}")

    # Write Manifest substitute top_layer_id
    manifest_data['layers'][-1]['digest'] = "sha256:" + new_layer_hash
    manifest_data['layers'][-1]['size'] = os.path.getsize(image_dir + '/blobs/sha256/' + new_layer_hash)
    manifest_data['config']['digest'] = "sha256:" + new_config_hash
    manifest_data['config']['size'] = os.path.getsize(image_dir + '/blobs/sha256/' + new_config_hash)
    manifest_handle.seek(0)
    json.dump(manifest_data, manifest_handle, ensure_ascii=False)
    manifest_handle.truncate()
    manifest_handle.close()
    new_manifest_hash = get_sha256(manifest_path)
    os.rename(manifest_path, image_dir + '/blobs/sha256/' + new_manifest_hash)
    print(f"manigest_hash: {config_hash} -> new_manifest_hash: {new_manifest_hash}")

    # Write index.json substitute config_id
    index_data['manifests'][0]['digest'] = "sha256:" + new_manifest_hash
    index_data['manifests'][0]['size'] = os.path.getsize(image_dir + '/blobs/sha256/' +new_manifest_hash)
    index_handle.seek(0)
    json.dump(index_data, index_handle, ensure_ascii=False)
    index_handle.truncate()
    index_handle.close()

    # package new image
    subprocess.run(['tar', '-cf', restored_image, '-C', image_dir, '.'])

# upgrage image layer with file and back up 
def substitute_layer_with_backup(diff_content = diff_content, substitution_way = 'all', backup_way = 'file'):
    with open(diff_content + '/diff.txt', 'r') as f:
        lines = f.readlines()
    for line in lines:
        change_list = line.split(" ")
        file_name = change_list[1].strip()
        file_path = staged_layer + '/app/' + file_name
        if line.startswith('-f'):
            if os.path.isfile(file_path):
                os.rename(file_path, f"{backup_dir}/{image_name}/diff_content/{file_name}")
                print(f"Delete file and backup : {file_path}")
            else:
                print(f"file {file_path} doesn't exist")

        elif line.startswith('-d'):
            if os.path.isdir(file_path):
                os.rename(file_path, f"{backup_dir}/{image_name}/diff_content/{file_name}")
                print(f"Delete folder and backup : {file_path}")
            else:
                print(f"folder {file_path} doesn't exist")

        elif line.startswith('+f'):
            if not os.path.isfile(file_path):
                os.rename(diff_content + '/' + file_name, file_path)
                print(f"Move file: {file_path}")
            else:
                print(f"The file already exists.")

        elif line.startswith('+d'):
            if not os.path.isdir(file_path):
                os.rename(diff_content + '/' + file_name, file_path)
                print(f"Move folder: {file_path}")
            else:
                print(f"The folder already exists.")

        elif line.startswith('~'):
            if substitution_way == 'all': # It can only achieve file-level backup
                os.rename(file_path, f"{backup_dir}/{image_name}/diff_content/{file_name}")
                os.rename(diff_content + '/' + file_name, file_path)
            elif substitution_way == 'inc':
                # Read content once
                with open(diff_content + '/' + file_name, 'r') as file:
                    updated_lines = file.readlines()
                # If backup_way is 'file', write the file, else don't need to back up
                if backup_way == 'file':
                    with open(f"{backup_dir}/{image_name}/diff_content/{file_name}", 'w') as file:
                        file.writelines(updated_lines)
                with open(file_path, 'r+') as file:
                    update_file = file.readlines()
                    location_update_file = 0
                    location_updated_lines = 0 # location of diff file

                    for i in range(2, len(change_list), 2):
                        if change_list[i] == 'R':
                            location_update_file += int(change_list[i + 1])

                        elif change_list[i] == 'D':
                            del update_file[location_update_file: location_update_file + int(change_list[i + 1])]
                          
                        elif change_list[i] == 'I':
                            for j in range(location_update_file, location_update_file + int(change_list[i + 1])):
                                update_file.insert(j, updated_lines[location_updated_lines])
                                location_updated_lines += 1

                            location_update_file += int(change_list[i + 1])
                    file.seek(0)
                    file.writelines(update_file)
                    file.truncate()
                print(f"Successfully completed the modification file: {file_path}")
        else:
            print(f"Unrecognized line: {line}")

def update_file(target_path, extracted_lines, change_list, is_text):
    if is_text:
        with open(extracted_lines, 'r') as file:
            extracted_lines = file.readlines()
        with open(target_path, 'r+') as file:
            target_file = file.readlines()
            location_target_file = 0
            location_extracted_lines = 0 # location of diff file

            for i in range(2, len(change_list), 2):
                if change_list[i] == 'R':
                    location_target_file += int(change_list[i + 1])
                elif change_list[i] == 'D':
                    del target_file[location_target_file: location_target_file + int(change_list[i + 1])]
                elif change_list[i] == 'I':
                    for j in range(location_target_file, location_target_file + int(change_list[i + 1])):
                        target_file.insert(j, extracted_lines[location_extracted_lines])
                        location_extracted_lines += 1
                    location_target_file += int(change_list[i + 1])
            file.seek(0)
            file.writelines(target_file)
            file.truncate()
    else:
        with open(extracted_lines, 'rb') as file:
            extracted_lines = file.read()
        with open(target_path, 'rb+') as file:
            target_file = bytearray(file.read())
            location_target_file = 0
            location_extracted_lines = 0 # location of diff file

            for i in range(2, len(change_list), 2):
                if change_list[i] == 'R':
                    location_target_file += int(change_list[i + 1])
                elif change_list[i] == 'D':
                    del target_file[location_target_file: location_target_file + int(change_list[i + 1])]
                elif change_list[i] == 'I':
                    for j in range(location_target_file, location_target_file + int(change_list[i + 1])):
                        target_file.insert(j, extracted_lines[location_extracted_lines])
                        location_extracted_lines += 1
                    location_target_file += int(change_list[i + 1])
            file.seek(0)
            file.write(target_file)
            file.truncate()
    print(f"Successfully completed the modification file: {target_path}")

# upgrade image layer and don't back up 
def substitute_layer_without_backup(diff_content = diff_content, substitution_way = 'inc'):
    with open(diff_content + '/diff.txt', 'r') as f:
        lines = f.readlines()
    for line in lines:
        change_list = line.split(" ")
        file_name = change_list[1].strip()
        file_path = staged_layer + '/app/' + file_name
        if line.startswith('-f'):
            if os.path.isfile(file_path):
                os.remove(file_path)
                print(f"Delete file: {file_path}")
            else:
                print(f"file {file_path} doesn't exist")
        elif line.startswith('-d'):
            if os.path.isdir(file_path):
                shutil.rmtree(file_path)
                print(f"Delete folder: {file_path}")
            else:
                print(f"folder {file_path} doesn't exist")
        elif line.startswith('+f'):
            if not os.path.isfile(file_path):
                os.rename(diff_content + '/' + file_name, file_path)
                print(f"Add file: {file_path}")
            else:
                print(f"The file already exists.")
        elif line.startswith('+d'):
            if not os.path.isdir(file_path):
                os.rename(diff_content + '/' + file_name, file_path)
                print(f"Add folder: {file_path}")
            else:
                print(f"The folder already exists.")
        elif line.startswith('~ '):
            os.remove(file_path)
            os.rename(diff_content + '/' + file_name, file_path)
            print(f"Move file{diff_content + '/' + file_name} to {file_path}")
        elif line.startswith('~t'):
            update_file(file_path, diff_content + '/' + file_name, change_list, is_text = True)
        elif line.startswith('~b'):
            update_file(file_path, diff_content + '/' + file_name, change_list, is_text = False)
        else:
            print(f"Unrecognized line: {line}")

def upgrade_image(compressed_diff_content = 'workspace/diff_content.tar.gz',
                  original_image = "workspace/testappoci.tar",
                  upgraded_image = 'workspace/new_image.tar',
                  substitution_way = 'inc',
                  back_up_way = 'layer'):

    global layer_time # to change global variable for recording time
    # unpack diff_content and image
    start_unpack = time.time()
    layer_time['unpack_start'] = time.time() # time
    subprocess.run(['tar', '-xzf', compressed_diff_content, '-C', staged_diff_content])
    layer_time['unpack_end'] = time.time() # time
    subprocess.run(['tar', '-xf', original_image , '-C', image_dir])
    print(f"unpack=============================={(time.time() - start_unpack) * 1000}")

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


    # extract top layer
    start_extract = time.time()
    subprocess.run(['tar', '-xf', f"{image_dir}/blobs/sha256/{top_layer_hash}", '-C', staged_layer])
    print("Successfully extacted top layer")
    print(f"extract=============================={(time.time() - start_extract) * 1000}")

    # back up layer and remove old top layer, its change is diff_content and staged_layer and backupdir
    if back_up_way == 'layer':
        layer_time['backup_start'] = time.time() # time
        back_up_layer(top_layer_hash)
        layer_time['substitute_start'] = time.time() # time
        substitute_layer_without_backup(substitution_way = substitution_way)
        layer_time['substitute_end'] = time.time() # time
    elif back_up_way == 'file':
        # global file_time
        # file_time['sub_backup_start_time'] = time.time() # time
        os.remove(f"{image_dir}/blobs/sha256/{top_layer_hash}")
        os.makedirs(f"{backup_dir}/{image_name}/diff_content")
        substitute_layer_with_backup(substitution_way = substitution_way, backup_way = 'file')
        file_time['sub_backup_end_time'] = time.time() # time
    elif back_up_way == 'code':
        os.remove(f"{image_dir}/blobs/sha256/{top_layer_hash}")
        os.makedirs(f"{backup_dir}/{image_name}/diff_content")
        substitute_layer_with_backup(substitution_way = substitution_way, backup_way = 'code')
    elif back_up_way == 'none':
        os.remove(f"{image_dir}/blobs/sha256/{top_layer_hash}")
        substitute_layer_without_backup(substitution_way = substitution_way)


    # repack new layer
    start_repack = time.time()
    subprocess.run(['tar', '-czf', 'workspace/tmp/new_layer.tar', '-C', staged_layer, '.'])
    print(f"repack=============================={(time.time() - start_repack) * 1000}")
    start_newhash = time.time()
    new_layer_hash = get_sha256("workspace/tmp/new_layer.tar")
    print(f"new_layer_hash=============================={(time.time() - start_newhash) * 1000}")
    start_test = time.time()
    new_layer_diff_id = get_gzip_layer_diff_id("workspace/tmp/new_layer.tar")
    print(f"diff_id=============================={(time.time() - start_test) * 1000}")
    diff_id_list[0] = new_layer_diff_id
    print(f"new layer_diff_id: {new_layer_diff_id}")

    # move new layer to image
    os.rename("workspace/tmp/new_layer.tar", image_dir + "/blobs/sha256/" + new_layer_hash)
    print(f"old_layer_hash: {top_layer_hash} -> new_layer_hash: {new_layer_hash}")

    # Write config: substitute top layer diff_id
    config_path = image_dir + '/blobs/sha256/' + config_hash
    with open(config_path, 'r+', encoding = 'utf-8') as config_handle:
        config_data = json.load(config_handle)
        config_data['rootfs']['diff_ids'][-1] = "sha256:" + new_layer_diff_id
        config_handle.seek(0)
        json.dump(config_data, config_handle, ensure_ascii=False)
        config_handle.truncate()
    new_config_hash = get_sha256(config_path)
    os.rename(config_path, image_dir + '/blobs/sha256/' + new_config_hash)
    print(f"config_hash: {config_hash} -> new_config_hash: {new_config_hash}")

    # Write Manifest: substitute top_layer_id
    manifest_data['layers'][-1]['digest'] = "sha256:" + new_layer_hash
    manifest_data['layers'][-1]['size'] = os.path.getsize(image_dir + '/blobs/sha256/' + new_layer_hash)
    manifest_data['config']['digest'] = "sha256:" + new_config_hash
    manifest_data['config']['size'] = os.path.getsize(image_dir + '/blobs/sha256/' + new_config_hash)
    manifest_handle.seek(0)
    json.dump(manifest_data, manifest_handle, ensure_ascii=False)
    manifest_handle.truncate()
    manifest_handle.close()
    new_manifest_hash = get_sha256(manifest_path)
    os.rename(manifest_path, image_dir + '/blobs/sha256/' + new_manifest_hash)
    print(f"manigest_hash: {config_hash} -> new_manifest_hash: {new_manifest_hash}")

    # Write index.json: substitute config_id
    index_data['manifests'][0]['digest'] = "sha256:" + new_manifest_hash
    index_data['manifests'][0]['size'] = os.path.getsize(image_dir + '/blobs/sha256/' +new_manifest_hash)
    index_handle.seek(0)
    json.dump(index_data, index_handle, ensure_ascii=False)
    index_handle.truncate()
    index_handle.close()

    # package new image
    start_package = time.time()
    subprocess.run(['tar', '-cf', upgraded_image, '-C', image_dir, '.'])
    print(f"package=============================={(time.time() - start_package) * 1000}")
    
def upgrade_image_with_layer(compressed_diff_content = 'workspace/diff_content.tar.gz',
                            original_image = "workspace/testappoci.tar",
                            upgraded_image = 'workspace/new_image.tar',
                            back_up_way = 'layer'):
    global layer_time # to change global variable for recording time
    # unpack diff_content and image
    layer_time['unpack_start'] = time.time() # time
    subprocess.run(['tar', '-xzf', compressed_diff_content, '-C', staged_diff_content])
    layer_time['unpack_end'] = time.time() # time
    subprocess.run(['tar', '-xf', original_image , '-C', image_dir])

    # read index.json and get manifest path
    index_handle = open(image_dir + '/index.json', 'r+')
    index_data = json.load(index_handle)
    manifests_digest = index_data['manifests'][0]['digest']
    manifest_path = image_dir + f"/blobs/sha256/{manifests_digest[7:]}"  # delete prefix "sha256:"

    # extact top layer's digest
    manifest_handle = open(manifest_path, 'r+')
    manifest_data = json.load(manifest_handle)
    top_layer_hash = manifest_data['layers'][-1]['digest'][7:]
    config_hash = manifest_data['config']['digest'][7:]

    # backup old layer
    if back_up_way == 'layer':
        layer_time['backup_start'] = time.time() # time
        back_up_layer(top_layer_hash)

    # sustitute layer
    layer_time['substitute_start'] = time.time() # time
    new_layer_hash = os.listdir(diff_content)[0]
    os.rename(f"{diff_content}/{new_layer_hash}", f"{image_dir}/blobs/sha256/{new_layer_hash}")
    layer_time['substitute_end'] = time.time() # time

    new_layer_diff_id = get_gzip_layer_diff_id(f"{image_dir}/blobs/sha256/{new_layer_hash}")
    diff_id_list[0] = new_layer_diff_id
    print(f"new layer_diff_id: {new_layer_diff_id}")

    # Write config: substitute top layer diff_id
    config_path = image_dir + '/blobs/sha256/' + config_hash
    with open(config_path, 'r+', encoding = 'utf-8') as config_handle:
        config_data = json.load(config_handle)
        config_data['rootfs']['diff_ids'][-1] = "sha256:" + new_layer_diff_id
        config_handle.seek(0)
        json.dump(config_data, config_handle, ensure_ascii=False)
        config_handle.truncate()
    new_config_hash = get_sha256(config_path)
    os.rename(config_path, image_dir + '/blobs/sha256/' + new_config_hash)
    print(f"config_hash: {config_hash} -> new_config_hash: {new_config_hash}")

    # Write Manifest substitute top_layer_id
    manifest_data['layers'][-1]['digest'] = "sha256:" + new_layer_hash
    manifest_data['layers'][-1]['size'] = os.path.getsize(image_dir + '/blobs/sha256/' + new_layer_hash)
    manifest_data['config']['digest'] = "sha256:" + new_config_hash
    manifest_data['config']['size'] = os.path.getsize(image_dir + '/blobs/sha256/' + new_config_hash)
    manifest_handle.seek(0)
    json.dump(manifest_data, manifest_handle, ensure_ascii=False)
    manifest_handle.truncate()
    manifest_handle.close()
    new_manifest_hash = get_sha256(manifest_path)
    os.rename(manifest_path, image_dir + '/blobs/sha256/' + new_manifest_hash)
    print(f"manigest_hash: {config_hash} -> new_manifest_hash: {new_manifest_hash}")

    # Write index.json substitute config_id
    index_data['manifests'][0]['digest'] = "sha256:" + new_manifest_hash
    index_data['manifests'][0]['size'] = os.path.getsize(image_dir + '/blobs/sha256/' +new_manifest_hash)
    index_handle.seek(0)
    json.dump(index_data, index_handle, ensure_ascii=False)
    index_handle.truncate()
    index_handle.close()

    # package new image
    subprocess.run(['tar', '-cf', upgraded_image, '-C', image_dir, '.'])

# workspace structure
# workspace
#     ├── tmp
#     │   ├── extract_dir
#     │   ├── staged_layer
#     │   ├── staged_diff_content
#     │   │   ├── diff_content
#     ├── backup
#     │   ├── testapp
#     │   │   ├── diff_content

layer_time = {}
file_time = {}
if __name__ == "__main__":
    # Get the substitution method
    substitution_way = sys.argv[1] # 'all' or 'inc' or 'layer'
    back_up_way = sys.argv[2]      # 'layer' or 'file'  or 'code' or 'none'

    for _ in range(1):
        # To restore
        remove_dir_children([image_dir, staged_layer, backup_dir, staged_diff_content])
        remove_file_or_dir(["workspace/new_image.tar", "workspace/new_docker_image.tar",
                            "workspace/new_restored_image.tar", "workspace/new_docker_restored_image.tar"])

        all_start_time = time.time() # time
        if substitution_way == 'layer':
            upgrade_image_with_layer(compressed_diff_content = 'workspace/diff_content.tar.gz',
                                     original_image = "workspace/testappoci.tar",
                                     upgraded_image = "workspace/new_image.tar",
                                     back_up_way = back_up_way)
        else:
            upgrade_image(compressed_diff_content = 'workspace/diff_content.tar.gz',
                          original_image = "workspace/testappoci.tar",
                          upgraded_image = "workspace/new_image.tar",
                          substitution_way = substitution_way,
                          back_up_way = back_up_way)
        upgrade_and_backup_time  = (time.time() - all_start_time) * 1000 # time

        # oci_to_docker(oci_image = "new_image.tar", docker_image = "new_docker_image.tar", tag = 'test') # To test middile stage

        # print("-----------------------------Restore-----------------------------")
        # if back_up_way == 'layer':
        #     remove_dir_children([image_dir, staged_layer, staged_diff_content])
        #     restore_start = time.time() # time
        #     back_layer_hash = os.listdir(backup_dir + '/' + image_name)[0]
        #     restore_with_layer(backup_layer_hash = back_layer_hash,
        #                        original_image = "workspace/new_image.tar",
        #                        restored_image = "workspace/new_restored_image.tar")
        #     restore_time = (time.time() - restore_start) * 1000 # time
            
            # oci_to_docker(oci_image = "new_restored_image.tar", docker_image = "new_docker_restored_image.tar", tag = 'test')

            # To write time
        with open(f'{substitution_way}_{back_up_way}.txt', 'a') as f:
            unpack_diff_time = (layer_time['unpack_end'] - layer_time['unpack_start']) * 1000
            backup_time = (layer_time['substitute_start'] - layer_time['backup_start']) * 1000
            substitute_time = (layer_time['substitute_end'] - layer_time['substitute_start']) * 1000
            upgrade_time = upgrade_and_backup_time - backup_time

            f.write(f"{upgrade_time}" + \
                    f" {unpack_diff_time}" + \
                    f" {backup_time}" + \
                    f" {substitute_time}\n"
                )
        # # elif back_up_way == 'file':
        # #     pack_start_time = time.time()
        # #     # make diff_file
        # #     invert_diff_file(diff_file = diff_content + '/diff.txt', target_path = f"{backup_dir}/{image_name}/diff_content/diff.txt", invert_change_path = False)
        # #     # pack diff_content
        #     subprocess.run(['tar', '-czf', f"{backup_dir}/{image_name}/diff_content.tar.gz", '-C', f"{backup_dir}/{image_name}", "diff_content"])
        #     pack_end_time = time.time()
        #     remove_dir_children([image_dir, staged_layer, staged_diff_content])
        #     restore_start_time = time.time()
        #     upgrade_image(compressed_diff_content = f"{backup_dir}/{image_name}/diff_content.tar.gz",
        #                   original_image = "workspace/new_image.tar",
        #                   upgraded_image = 'workspace/new_restored_image.tar',
        #                   substitution_way = 'all',
        #                   back_up_way = 'none')
        #     restore_end_time = time.time()
        #     # oci_to_docker(oci_image = "new_restored_image.tar", docker_image = "new_docker_restored_image.tar", tag = 'test')
            
        #     # To write time
        #     with open('workspace/data/all_file.txt', 'a') as f:
        #         f.write(f"total_time: {(upgrade_time + pack_end_time - pack_start_time + restore_end_time - restore_start_time) * 1000}, " + \
        #                 f"upgrade_time: {(upgrade_time + pack_end_time - pack_start_time) * 1000}, " + \
        #                 # f"sub_backup_time: {(file_time['sub_backup_end_time'] - file_time['sub_backup_start_time']) * 1000}, " + \
        #                 # f"pack_time: {(pack_end_time - pack_start_time) * 1000}, " + \
        #                 f"restore_time: {(restore_end_time - restore_start_time) * 1000}\n")
        # elif back_up_way == 'code':
        #     pack_start_time = time.time()
        #     # make diff_file
        #     invert_diff_file(diff_file = diff_content + '/diff.txt', target_path = f"{backup_dir}/{image_name}/diff_content/diff.txt", invert_change_path = True)
        #     back_up_changed_file_line(diff_file = f"{backup_dir}/{image_name}/diff_content/diff.txt")
        #     # pack diff_content
        #     subprocess.run(['tar', '-czf', f"{backup_dir}/{image_name}/diff_content.tar.gz", '-C', f"{backup_dir}/{image_name}", "diff_content"])
        #     pack_end_time = time.time()
        #     remove_dir_children([image_dir, staged_layer, staged_diff_content])
        #     restore_start_time = time.time()
        #     upgrade_image(compressed_diff_content = f"{backup_dir}/{image_name}/diff_content.tar.gz",
        #                   original_image = "workspace/new_image.tar",
        #                   upgraded_image = 'workspace/new_restored_image.tar',
        #                   substitution_way = 'inc',
        #                   back_up_way = 'none')
        #     restore_end_time = time.time()
        #     # oci_to_docker(oci_image = "new_restored_image.tar", docker_image = "new_docker_restored_image.tar", tag = 'test')

        # with open("workspace/test.txt", 'w') as f:
        #     for diff_id in diff_id_list:
        #         f.write(diff_id + '\n')