import sys

def find_non_ascii(filepath, output_path):
    with open(filepath, 'r', encoding='utf-8') as f:
        with open(output_path, 'w', encoding='utf-8') as out:
            for i, line in enumerate(f, 1):
                if any(ord(c) > 127 for c in line):
                    out.write(f"{i}: {line}")

if __name__ == "__main__":
    find_non_ascii(sys.argv[1], sys.argv[2])
