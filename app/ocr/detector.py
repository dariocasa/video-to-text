from __future__ import annotations

import cv2
import numpy as np


def find_horizontal_split(image: np.ndarray, search_range: tuple[float, float] = (0.3, 0.7)) -> int:
    """
    Find the Y-coordinate of the horizontal split between sections.
    Detects the first row that belongs to the white background section, 
    which is robust across all quiz layouts.
    """
    height = image.shape[0]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Calculate median intensity for each row (ignores text horizontal lines)
    row_medians = np.median(gray, axis=1).astype(np.uint8)

    # Apply a median filter along the Y-axis to erase text-induced spikes
    filtered_medians = cv2.medianBlur(row_medians.reshape(-1, 1), 11).flatten()

    # Search for the split within a safe central region of the image
    min_y = int(height * search_range[0])
    max_y = int(height * search_range[1])

    # Find the FIRST row in the filtered signal that reaches a "white background" level
    # This is more robust than looking for the maximum difference.
    white_threshold = 240
    white_indices = np.where(filtered_medians[min_y:max_y] > white_threshold)[0]
    
    if len(white_indices) > 0:
        # We take the first white row and go up a few pixels to capture the full white area
        split_y = white_indices[0] + min_y - 2
    else:
        # Fallback to the maximum intensity difference if no white section is detected
        diffs = np.abs(np.diff(filtered_medians))
        split_y = int(np.argmax(diffs[min_y : max_y]) + min_y)

    return int(split_y)
