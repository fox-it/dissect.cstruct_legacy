from setuptools import setup

with open("README.md") as fh:
    long_description = fh.read()

setup(
    name="dissect.cstruct",
    author="Fox-IT",
    description="Structure parsing in Python made easy.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    license="MIT",
    keywords="cstruct struct dissect structure binary pack packer unpack unpacker parser parsing",
    url="https://github.com/fox-it/dissect.cstruct",
    namespace_packages=['dissect'],
    packages=['dissect.cstruct', 'dissect.cstruct.types'],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License"
    ]
)
