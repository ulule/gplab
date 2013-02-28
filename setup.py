import os
from collections import defaultdict

from distutils.core import setup

from setuptools import find_packages

import gplab

root = os.path.normpath(os.path.dirname(os.path.abspath(__file__)))


with open('requirements.txt') as reqs:
    install_requires = reqs.read().split('\n')


def get_dir_files(root_directory, dirname):
    directories = defaultdict(list)

    root_dir = os.path.join(root_directory, dirname)

    for root, dirs, files in os.walk(root_dir): 
        for file in files:
            current_dir = os.path.join(root, file)[len(root_dir):]
            if current_dir.startswith('.'):
                continue

            directories[os.path.dirname(os.path.join(dirname, current_dir))].append(os.path.join(root, file))

    return directories.items()

static_files = get_dir_files(os.path.join(root, gplab.__title__), 'static/')
static_files += get_dir_files(os.path.join(root, gplab.__title__), 'conf/')

setup(
    name=gplab.__title__,
    version=gplab.__version__,
    data_files=static_files,
    long_description=__doc__,
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=install_requires
)
