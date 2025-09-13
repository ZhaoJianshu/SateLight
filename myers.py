import hashlib

def read_lines(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.readlines()

# print percentage
def pct_print(route, source):
    prev_x = 0
    prev_y = 0
    added_num = 0
    removed_num = 0
    for i in range(len(route)):
        x, y = route[i]
        if x > prev_x and y > prev_y:
            pass
        elif x > prev_x:
            removed_num += 1
        else:
            added_num += 1
        prev_x, prev_y = x, y

    file_pct = (added_num + removed_num) / (len(source) + added_num) * 100
    print(f"The file changed by {file_pct:.2f}%")

def diff_print(route, source, dest):
    prev_x, prev_y = 0, 0
    for i in range(1, len(route)):
        x, y = route[i]
        if x > prev_x and y > prev_y:
            print("     {:<5} {:<5} {}".format(prev_x + 1, prev_y + 1, source[prev_x]))
        elif x > prev_x:
            print("-    {:<5} {:<5} {}".format(prev_x + 1, " ", source[prev_x]))
        else:
            print("+    {:<5} {:<5} {}".format(" ", prev_y + 1, dest[prev_y]))
        prev_x, prev_y = x, y

def find_route(trace, max_steps, x, y):
    # print("max_steps",max_steps)
    # print("initial k: ",x - y)
    # print("k range: ",-y, x)
    route = []
    for d in range(max_steps, 0, -1):
        k = x - y
        if k == -d or (k != d and trace[d - 1][k - 1] < trace[d - 1][k + 1]):
            prev_k = k + 1 # move down in positive direction
        else:
            prev_k = k - 1 # move right in positive direction
        prev_x = trace[d - 1][prev_k]
        prev_y = prev_x - prev_k
        route.insert(0, (x ,y))
        while x > prev_x and y > prev_y:
            x, y = x - 1, y - 1
            route.insert(0, (x ,y))
        x, y = prev_x, prev_y
        if d == 1:
            while x >= 0:
                route.insert(0, (x ,y))
                x, y = x - 1, y - 1

    # print("route", route)
    return route

def myers(source, dest):
    m = len(source)
    n = len(dest)
    diagonals = set()
    for x in range(m):
        for y in range(n):
            if source[x] == dest[y]:
                diagonals.add((x,y))
    v = {} # the location of x
    for d in range(m + n + 1): # depth from 0 to m + n
        v[d] = [-1 for _ in range((m + n) * 2 + 1)] # the location of x in every diagonal of depth
        for k in range(-d, d + 1, 2):
            if k == -d or (k != d and v[d - 1][k - 1] < v[d - 1][k + 1]):
                if d == 0:
                    x = 0
                else:
                    x = v[d - 1][k + 1] # move down
            else:
                x = v[d - 1][k - 1] + 1 # move right

            y = x - k

            while(x < m and y < n and (x, y) in diagonals):
                x = x + 1
                y = y + 1
            
            if x < 0:
                print("Error, x < 0")
            v[d][k] = x
            if x >= m and y >= n:
                route = find_route(v, d, m, n)
                return route

def text_get_diff0(source, dest):
    source_lines = read_lines(source)
    dest_lines   = read_lines(dest)
    route = myers(source_lines, dest_lines)
    edit_path = get_edit_path(route)
    return edit_path

def text_get_diff(source, dest):
    source_lines = read_lines(source)
    dest_lines   = read_lines(dest)
    route = op_myers(source_lines, dest_lines)
    edit_path = get_edit_path(route)
    return edit_path


def read_bytes(file_path):
    with open(file_path, 'rb') as file:
        return file.read()

def get_chunks_hash(file_path, end):
    bytes_content = read_bytes(file_path)
    hash_chunks = []
    start_location = 0
    for i in range(len(end)):
        chunk = bytes_content[start_location:end[i] + 1]
        start_location = end[i] + 1
        hash_value = hashlib.sha1(chunk).hexdigest()
        hash_chunks.append(hash_value)
    return hash_chunks

def get_edit_path(route):
    prev_x, prev_y, prev_move = 0, 0, 'B' # 'B' can be any value different from 'R', 'D', 'I'
    edit_path = []
    for i in range(1, len(route)):
        x, y = route[i]
        if x > prev_x and y > prev_y:
            move = 'R'
            if move != prev_move:
                edit_path.append(["R", 1]) # 'R' means to ratain the line of code
            else:
                edit_path[-1][1] += 1
        elif x > prev_x:
            move = 'D'
            if move != prev_move:
                edit_path.append(["D", 1])
            else:
                edit_path[-1][1] += 1 # 'D' means to delete the line of code
        elif y > prev_y:
            move = 'I'
            if move != prev_move:
                edit_path.append(["I", 1]) # 'I' means to insert the line of code
            else:
                edit_path[-1][1] += 1
        else:
            print("Error: get_edit_path")
        prev_x, prev_y, prev_move = x, y, move
    return edit_path

def get_chunks_length(chunks_end):
    chunks_length = []
    prev_last = -1
    for i in range(len(chunks_end)):
        chunks_length.append(chunks_end[i] - prev_last)
        prev_last = chunks_end[i]
    return chunks_length

def chunks_to_bytes(edit_path, source_chunks_length, dest_chunks_length):
    # Convert the chunks edit path to bytes edit path
    bytes_edit_path = []
    x, y = 0, 0 # chunks'location of source chunks and dest chunks
    # print("edit_path", edit_path)
    # print("source_chunks_length", source_chunks_length)
    # print("dest_chunks_length", dest_chunks_length)
    for i in range(len(edit_path)):
        # print(f"edit_path[{i}]", edit_path[i])
        # print("x", x)
        # print("y", y)
        if edit_path[i][0] == 'R':
            bytes_edit_path.append(['R', 0])
            for j in range(edit_path[i][1]):
                bytes_edit_path[-1][1] += source_chunks_length[x + j]
            x += edit_path[i][1]
            y += edit_path[i][1]
        elif edit_path[i][0] == 'D':
            bytes_edit_path.append(['D', 0])
            for j in range(edit_path[i][1]):
                bytes_edit_path[-1][1] += source_chunks_length[x + j]
            x += edit_path[i][1]
        elif edit_path[i][0] == 'I':
            bytes_edit_path.append(['I', 0])
            for j in range(edit_path[i][1]):
                bytes_edit_path[-1][1] += dest_chunks_length[y + j]
            y += edit_path[i][1]
    return bytes_edit_path

def binary_get_diff0(source, dest, source_end, dest_end):
    source_chunks = get_chunks_hash(source, source_end)
    dest_chunks = get_chunks_hash(dest, dest_end)
    route = myers(source_chunks, dest_chunks)
    edit_path = get_edit_path(route)
    # print("source_end", source_end)
    # print("dest_end", dest_end)
    source_chunks_length = get_chunks_length(source_end)
    dest_chunks_length = get_chunks_length(dest_end)
    bytes_edit_path = chunks_to_bytes(edit_path, source_chunks_length, dest_chunks_length)
    return bytes_edit_path

def binary_get_diff(source, dest, source_end, dest_end):
    source_chunks = get_chunks_hash(source, source_end)
    dest_chunks = get_chunks_hash(dest, dest_end)
    route = op_myers(source_chunks, dest_chunks)
    # print("route", route)
    edit_path = get_edit_path(route)
    # print("route_end", route[-1])
    # print("len(source_end)", len(source_end))
    # print("len(dest_end)", len(dest_end))
    source_chunks_length = get_chunks_length(source_end)
    dest_chunks_length = get_chunks_length(dest_end)
    bytes_edit_path = chunks_to_bytes(edit_path, source_chunks_length, dest_chunks_length)
    return bytes_edit_path

def get_middle_snake(s_x, s_y, e_x, e_y, source_list, dest_list):
    # print(f"get_middle_snake:s_x: {s_x},s_y: {s_y},e_x: {e_x},e_y: {e_y}")
    start_k, end_k = s_x - s_y, e_x - e_y
    start_p, end_p = start_k % 2, end_k % 2
    max_mid_d = (e_x + e_y - s_x -s_y) // 2 + 1
    v_start = {i: -1 for i in range(s_x - e_y, e_x - s_y + 1)}
    v_end = {i: e_x + 1 for i in range(s_x - e_y, e_x - s_y + 1)}
    for d in range(0, max_mid_d + 1):
        for k in range(start_k - d, start_k + d + 1, 2):
            if k == start_k - d or (k != start_k + d and v_start[k - 1] < v_start[k + 1]):
                if d == 0:
                    x = s_x
                else:
                    x = v_start[k + 1] # move down
            else:
                x = v_start[k - 1] + 1 # move right
            y = x - k
            while(x < e_x and y < e_y and source_list[x] == dest_list[y]):
                x = x + 1
                y = y + 1
            
            v_start[k] = x
            if start_p != end_p and k in range(end_k - (d - 1), end_k + d ,2):
                if x >= v_end[k]:
                    if x == e_x and y ==e_y:
                        if k == start_k - 1:
                            return [[x, y - 1], [x, y - 1]]
                        elif k == start_k + 1:
                            return [[x - 1 ,y], [x - 1, y]]
                        else:
                            print("Error: get_middle_snake")
                    else:
                        return [[v_end[k], v_end[k] - k], [x, y]]

        for k in range(end_k - d, end_k + d + 1, 2):
            if k == end_k - d or (k != end_k + d and v_end[k + 1] - 1 <= v_end[k - 1]):
                if d == 0:
                    x = e_x
                else:
                    x = v_end[k + 1] - 1 # move left
            else:
                x = v_end[k - 1] # move up
            y = x - k
            while(x > s_x and y > s_y and source_list[x - 1] == dest_list[y - 1]):
                x = x - 1
                y = y - 1
            
            v_end[k] = x
            if start_p == end_p and k in range(start_k - d, start_k + d + 1 ,2):
                if x <= v_start[k]:
                    return [[x, y], [v_start[k], v_start[k] - k]]
    print('Error: get_middle_snake')

def LCS(s_x, s_y, e_x, e_y, source_list, dest_list):
    # print(f"LCS:s_x: {s_x},s_y: {s_y},e_x: {e_x},e_y: {e_y}")
    if e_x == s_x and e_y == s_y:
        return [[e_x, e_y]]
    elif e_x > s_x and e_y == s_y:
        return [[i, s_y] for i in range(s_x, e_x + 1)]
    elif e_y > s_y and e_x == s_x:
        return [[s_x, i] for i in range(s_y, e_y + 1)]
    elif e_x > s_x and e_y > s_y:
        m_snake = get_middle_snake(s_x, s_y, e_x, e_y, source_list, dest_list)
        # print('m_snake', m_snake)
        middle = [[m_snake[0][0] + i , m_snake[0][1] + i] for i in range(1, m_snake[1][0] - m_snake[0][0])]
        first = LCS(s_x, s_y, m_snake[0][0], m_snake[0][1], source_list, dest_list)
        latter = LCS(m_snake[1][0], m_snake[1][1], e_x, e_y, source_list, dest_list)
        if not middle and first and latter and first[-1] == latter[0]:
                return first + latter[1:]
        return first + middle + latter
    else:
        print(f"LCS Error:s_x:{s_x}, s_y{s_y}, e_x{e_x}, e_y{e_y}")
    
def op_myers(source, dest):
    m = len(source)
    n = len(dest)
    return LCS(0, 0, m, n, source, dest)


if __name__ == "__main__":
    binary_get_diff('/home/breeze/test/1/core_nf_simulation', '/home/breeze/test/2/core_nf_simulation')
    # print(text_get_diff('/home/breeze/encode/app/encoding.py', '/home/breeze/encode/0changed2/encoding.py'))
    # text_get_diff2('/home/breeze/yolov3/before_yolo/benchmarks.py', '/home/breeze/yolov3/0changed8/benchmarks.py')
    # print(text_get_diff2('/home/breeze/yolov3/before_yolo/benchmarks.py', '/home/breeze/yolov3/0changed8/benchmarks.py'))
    # a = ['a', 'b', 'c', 'a', 'b', 'b', 'a']
    # b = ['c', 'b', 'a', 'b', 'a', 'c']
    # print(op_myers(a, b))