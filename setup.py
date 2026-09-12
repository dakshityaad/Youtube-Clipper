from setuptools import setup, find_packages

setup(
    name="youtube-clipper",
    version="1.1.0",
    packages=find_packages(),
    py_modules=["cli"],
    install_requires=[
        "yt-dlp>=2024.1.0",
        "openai-whisper>=20231117",
        "click>=8.0.0",
    ],
    entry_points={
        "console_scripts": [
            "clipper=cli:cli",
        ],
    },
    python_requires=">=3.8",
    author="Dakshit Yadav",
    license="MIT",
    description="Extract, crop, and caption YouTube video clips",
)
