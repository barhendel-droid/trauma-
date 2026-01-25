import re

with open('web/index.html', 'r') as f:
    content = f.read()

tokens = re.findall(r'<(/?div|/?section|/?main|/?body|/?html)\b', content)
balance = 0
for i, token in enumerate(tokens):
    if token.startswith('/'):
        balance -= 1
    else:
        balance += 1
    if balance < 0:
        print(f"Error: Negative balance at token {i}: {token}")
print(f"Final balance: {balance}")
