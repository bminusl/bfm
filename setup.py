import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="bfm",
    version="0.0.1",
    author="Bryton Lacquement",
    author_email="contact@bminusl.xyz",
    description="Yet another Vim-inspired file manager for the console.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/bminusl/bfm",
    project_urls={
        "Bug Tracker": "https://github.com/bminusl/bfm/issues",
    },
    classifiers=[
        "Environment :: Console",
        "Environment :: Console :: Curses",
        "Intended Audience :: Developers",
        "Intended Audience :: End Users/Desktop",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Programming Language :: Python :: 3",
        "Operating System :: POSIX",
        "Operating System :: Unix",
        "Topic :: Desktop Environment :: File Managers",
        "Topic :: Utilities",
    ],
    package_dir={"bfm": "bfm"},
    packages=setuptools.find_packages(),
    python_requires=">=3.5",
    install_requires=[
        "humanize",
        "urwid",
    ],
)
