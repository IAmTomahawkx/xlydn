import os.path

for dir, subdirs, files in os.walk("."):
    if 'venv' in dir or 'locale' in dir:
        continue
    for file in files:
        if file.endswith('.py'):
            fname = os.path.join(dir, file)
            print(fname)