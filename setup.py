from setuptools import setup,find_packages

with open("requirements.txt") as f:
    requirements = f.read().splitlines()

setup(
    name="careercoach-ai",
    version="0.1",
    author="Ru-Dipity",
    packages=find_packages(),
    install_requires = requirements,
)