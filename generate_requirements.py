import os
import re

# Directorio del proyecto
project_dir = '/home/javierh/Desenvolupament/personal/porraMotoGP'

# Expresión regular para encontrar importaciones
import_re = re.compile(r'^\s*(?:import|from)\s+([a-zA-Z0-9_]+)')

# Módulos estándar de Python
standard_libs = set([
    'abc', 'argparse', 'array', 'asyncio', 'base64', 'binascii', 'bisect', 'builtins', 'calendar', 'cmath', 'collections',
    'concurrent', 'contextlib', 'copy', 'copyreg', 'cProfile', 'csv', 'ctypes', 'datetime', 'decimal', 'difflib', 'dis',
    'doctest', 'enum', 'errno', 'faulthandler', 'filecmp', 'fileinput', 'fnmatch', 'fractions', 'functools', 'gc', 'getopt',
    'getpass', 'gettext', 'glob', 'gzip', 'hashlib', 'heapq', 'hmac', 'html', 'http', 'imaplib', 'imghdr', 'imp', 'importlib',
    'inspect', 'io', 'itertools', 'json', 'keyword', 'linecache', 'locale', 'logging', 'lzma', 'mailbox', 'math', 'mimetypes',
    'modulefinder', 'multiprocessing', 'numbers', 'operator', 'os', 'pathlib', 'pickle', 'pickletools', 'pkgutil', 'platform',
    'plistlib', 'pprint', 'profile', 'pstats', 'py_compile', 'pydoc', 'queue', 'random', 're', 'reprlib', 'rlcompleter',
    'runpy', 'sched', 'secrets', 'selectors', 'shelve', 'shlex', 'shutil', 'signal', 'site', 'smtplib', 'socket', 'socketserver',
    'sqlite3', 'ssl', 'stat', 'statistics', 'string', 'stringprep', 'struct', 'subprocess', 'sunau', 'symtable', 'sys', 'sysconfig',
    'tabnanny', 'tarfile', 'tempfile', 'textwrap', 'threading', 'time', 'timeit', 'trace', 'traceback', 'tracemalloc', 'types',
    'typing', 'unittest', 'urllib', 'uuid', 'venv', 'warnings', 'wave', 'weakref', 'webbrowser', 'xml', 'xmlrpc', 'zipfile', 'zipimport',
    'zlib'
])

# Encontrar todos los archivos .py en el directorio del proyecto
py_files = []
for root, dirs, files in os.walk(project_dir):
    for file in files:
        if file.endswith('.py'):
            py_files.append(os.path.join(root, file))

# Encontrar todas las importaciones
imported_modules = set()
for py_file in py_files:
    with open(py_file, 'r') as f:
        for line in f:
            match = import_re.match(line)
            if match:
                module = match.group(1).split('.')[0]
                if module not in standard_libs:
                    imported_modules.add(module)

# Crear el archivo requirements.txt
with open('requirements.txt', 'w') as f:
    for module in sorted(imported_modules):
        f.write(f"{module}\n")

print("requirements.txt has been generated.")
