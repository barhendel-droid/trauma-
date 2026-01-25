import re

with open('web/index.html', 'r') as f:
    lines = f.readlines()

balance = 0
for i, line in enumerate(lines):
    line_num = i + 1
    # Find all opening and closing div/section tags
    tags = re.findall(r'<(/?div|/?section|/?main)\b', line)
    for tag in tags:
        if tag.startswith('/'):
            balance -= 1
        else:
            balance += 1
        if balance < 0:
            print(f"L{line_num}: Balance went negative ({balance}) at {tag}")
