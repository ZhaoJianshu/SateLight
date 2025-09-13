import os
import random
import magic
import file_change

def print_file_tpye(file_map):
    for value in file_map.values():
        mime = magic.from_file(value, mime=True)
        print(f"File: {value}, Type: {mime}")

def is_text_file(file_path):
    mime = magic.from_file(file_path, mime=True)
    return mime.startswith("text/")

def all_map_to_text_map(file_map):
    keys_to_delete = [key for key, value in file_map.items() if not is_text_file(value)]
    for key in keys_to_delete:
        del file_map[key]
    return file_map

def is_python_file(file_path):
    return file_path.endswith(".py")

def all_map_to_python_map(file_map):
    keys_to_delete = [key for key, value in file_map.items() if not is_python_file(value)]
    for key in keys_to_delete:
        del file_map[key]
    return file_map

def get_all_files(directory):
    file_map = {}
    for root, _, files in os.walk(directory):
        for file in files:
            abs_path = os.path.join(root, file)
            rel_path = os.path.relpath(abs_path, directory)
            file_map[rel_path] = abs_path
    return file_map

def select_random_files(file_map):
    num_to_select = random.randint(20, len(file_map))
    selected_files = random.sample(list(file_map.values()), num_to_select)
    return selected_files

def get_num_of_lines_in_dir(file_map):
    num = 0
    for file in file_map.values():
        if is_text_file(file):
            with open(file, "r") as f:
                line_count = sum(1 for _ in f)
            num += line_count
    return num

def get_num_of_bytes_in_dir(file_map):
    num = 0
    for file in file_map.values():
            num += os.path.getsize(file)
    return num

def generate_random_segments(sum_total, count):
    cuts = sorted(random.sample(range(sum_total + 1), count - 1))
    segments = [cuts[0]] + [cuts[i] - cuts[i - 1] for i in range(1, count - 1)] + [sum_total - cuts[-1]]
    return segments

def generate_fair_random_segments(sum_total, count, variance = 1000):
    avg = sum_total // count
    segments = [avg] * count

    remaining = sum_total - sum(segments)

    for _ in range(remaining):
        segments[random.randint(0, count - 1)] += 1

    for i in range(count):
        max_down = min(segments[i], variance)
        delta = random.randint(-max_down, variance)
        segments[i] += delta

    total = sum(segments)
    diff = total - sum_total

    while diff != 0:
        i = random.randint(0, count - 1)
        if diff > 0 and segments[i] > 0:
            segments[i] -= 1
            diff -= 1
        elif diff < 0:
            segments[i] += 1
            diff += 1

    return segments

def count_non_zero_elements(lst):
    return sum(1 for x in lst if x != 0)

change_rate = 0.1
length_of_line  = 6400
if __name__ == "__main__":
    file_map = get_all_files("/home/breeze/yolo/1")
    # print_file_tpye(file_map)
    total_bytes = get_num_of_bytes_in_dir(file_map)
    print("total_bytes", total_bytes)
    inserted_bytes = int(change_rate / (1 - change_rate) * total_bytes)
    change_lines = int(inserted_bytes / length_of_line)

    print("num_change_lines", change_lines)
    py_file_map = all_map_to_python_map(file_map)
    print("num_py_files", len(py_file_map))
    selected_files = select_random_files(py_file_map)
    segments = generate_fair_random_segments(sum_total = change_lines, count = len(selected_files), variance = 1000)
    print("num_selected_files", count_non_zero_elements(segments))
    print("segments", segments)
    changed_files = dict(zip(selected_files, segments))
    delete_sum, add_sum = 0, 0
    for key, value in changed_files.items():
        print(f"Change file: {key}, Lines to change: {value}")
        delete_num, add_num = file_change.file_change(key, value)
