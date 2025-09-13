import re
import random

blank_line_p = r"^\s*$"
comment_line_p = r"^\s*#.*$"
print_line_p = r"^\s*print\(.*\)\s*$"
def get_num_can_be_deleted_lines(file_path):
    total_lines = 0
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    for line in lines:
        if re.match(blank_line_p, line) or re.match(comment_line_p, line) or re.match(print_line_p, line):
            total_lines += 1
    return total_lines

def get_locations_of_lines_endwith_colon(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    locations = []
    for i, line in enumerate(lines):
        if line.endswith(":\n"):
            locations.append(i)
    return locations

def get_add_list(total_num, next_num, space_num):
    add_list = []
    for _ in range(total_num):
        choice = random.randint(0, 2)
        if choice == 0:
            add_list.append(' ' * space_num + f"#{next_num} " + '-' * (6400 - space_num - len(f"#{next_num} ") - 1) + '\n')
            next_num += 1
        elif choice == 1:
            add_list.append(' ' * space_num + f"print({next_num})" + '-' * (6400 - space_num - len(f"print({next_num})")) + "# line marker\n")
            next_num += 1
        elif choice == 2:
            add_list.append(' ' * space_num + f"unused_variable{next_num} = 0" + '-' * (6400 - space_num - len(f"unused_variable{next_num} = 0")) + "# unused\n")
            next_num += 1
    return add_list

def insert_harmless_code(file_path, num_insert):
    locations = get_locations_of_lines_endwith_colon(file_path)

    with open(file_path, 'r') as file:
        lines = file.readlines()

    next_num = 0
    if len(locations) == 0:
        lines[0:num_insert] = get_add_list(num_insert, next_num, 0)
        with open(file_path, 'w') as file:
            file.writelines(lines)
        return
    negative_index = 1
    while(num_insert > 0):
        if negative_index >= len(locations):
            space_num = len(lines[locations[-negative_index]]) - len(lines[locations[-negative_index]].lstrip()) + 4
            lines[locations[-negative_index] + 1:locations[-negative_index] + 1] = get_add_list(num_insert, next_num, space_num)
            num_insert = 0
        else:
            cur_insert_num = random.randint(1, num_insert)
            space_num = len(lines[locations[-negative_index]]) - len(lines[locations[-negative_index]].lstrip()) + 4
            lines[locations[-negative_index] + 1:locations[-negative_index] + 1] = get_add_list(cur_insert_num, next_num, space_num)
            next_num += cur_insert_num
            num_insert -= cur_insert_num
        negative_index += 1
    with open(file_path, 'w') as file:
        file.writelines(lines)

def delete_lines(file_path, num_deletes):
    with open(file_path, 'r') as file:
        lines = file.readlines()
    line_index = 0
    while num_deletes > 0:
        if re.match(blank_line_p, lines[line_index]) or re.match(comment_line_p, lines[line_index]):
            lines.pop(line_index)
            num_deletes -= 1
        elif re.match(print_line_p, lines[line_index]) and line_index > 0:
            if lines[line_index - 1].endswith(":\n"):
                num_space = len(lines[line_index - 1]) - len(lines[line_index - 1].lstrip()) + 4
                lines[line_index] = ' ' * num_space + 'pass\n'
                num_deletes -= 1
            else:
                lines.pop(line_index)
                num_deletes -= 1
        else:
            line_index += 1
        
    with open(file_path, 'w') as file:
        file.writelines(lines)


            
def file_change(file_path, num_changes):
    half_num_changes = num_changes // 2
    num_can_be_deleted_lines = get_num_can_be_deleted_lines(file_path)
    need_to_delete_lines = min(num_can_be_deleted_lines, half_num_changes)
    print("need_to_delete_lines", need_to_delete_lines)
    delete_lines(file_path, need_to_delete_lines)
    num_can_be_inserted_lines = num_changes - need_to_delete_lines
    print("num_can_be_inserted_lines", num_can_be_inserted_lines)
    insert_harmless_code(file_path, num_can_be_inserted_lines)
    return need_to_delete_lines, num_can_be_inserted_lines


if __name__ == "__main__":
    insert_harmless_code("/home/breeze/yolo3/0changed5/0changed5.py", 10)