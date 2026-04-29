# SPDX-License-Identifier: MIT

import hashlib
import math
from PIL import Image


def _dct_1d(values: list[float]) -> list[float]:
    size = len(values)
    result = []

    for k in range(size):
        total = 0.0
        for n, value in enumerate(values):
            total += value * math.cos(math.pi * (n + 0.5) * k / size)
        result.append(total)

    return result


def _dct_2d(matrix: list[list[float]]) -> list[list[float]]:
    row_transformed = [_dct_1d(row) for row in matrix]
    size = len(row_transformed)
    result = [[0.0] * size for _ in range(size)]

    for column_index in range(size):
        column = [row[column_index] for row in row_transformed]
        transformed_column = _dct_1d(column)
        for row_index, value in enumerate(transformed_column):
            result[row_index][column_index] = value

    return result


def compute_phash(path: str) -> str | None:
    """
    Compute a perceptual hash for image files.

    This implementation keeps a pHash-style workflow:
    1. resize to 32x32 grayscale
    2. run a 2D DCT
    3. keep the top-left 8x8 low-frequency block
    4. compare values against the block median

    It returns None when the file cannot be decoded as an image.
    """
    try:
        with Image.open(path) as img:
            grayscale = img.convert("L").resize((32, 32))
            pixels = list(grayscale.tobytes())
    except Exception:
        return None

    matrix = [list(map(float, pixels[index:index + 32])) for index in range(0, len(pixels), 32)]
    dct_matrix = _dct_2d(matrix)
    low_frequency = [row[:8] for row in dct_matrix[:8]]

    # Exclude the DC coefficient when computing the median threshold.
    coefficients = [value for row in low_frequency for value in row][1:]
    median = sorted(coefficients)[len(coefficients) // 2]

    bits = "".join(
        "1" if value >= median else "0"
        for row in low_frequency
        for value in row
    )

    return f"{int(bits, 2):016x}"


def phash_distance(left: str, right: str) -> int:
    # Compare perceptual hashes using Hamming distance.
    return bin(int(left, 16) ^ int(right, 16)).count("1")


def compute_file_hash(path: str, chunk_size: int = 1024 * 1024) -> str:
    # Use SHA-256 for exact duplicate detection across any supported file type.
    digest = hashlib.sha256()
    with open(path, "rb") as file_obj:
        while True:
            chunk = file_obj.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()
