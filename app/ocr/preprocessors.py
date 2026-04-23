from __future__ import annotations

import cv2
import numpy as np


def to_grayscale(image: np.ndarray) -> np.ndarray:
    """Convert an image to grayscale."""
    if len(image.shape) == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def invert_colors(image: np.ndarray) -> np.ndarray:
    """Invert image colors (useful for white text on dark background)."""
    return cv2.bitwise_not(image)


def apply_threshold(image: np.ndarray) -> np.ndarray:
    """Apply OTSU thresholding to a grayscale image."""
    _, thresholded = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return thresholded


def scale_image(image: np.ndarray, factor: float = 2.0) -> np.ndarray:
    """Scale the image by a given factor."""
    return cv2.resize(image, None, fx=factor, fy=factor, interpolation=cv2.INTER_CUBIC)


def denoise_image(image: np.ndarray, h: int = 10) -> np.ndarray:
    """Apply non-local means denoising to clean up artifacts."""
    return cv2.fastNlMeansDenoising(image, None, h, 7, 21)


def morph_open(image: np.ndarray, kernel_size: int = 2) -> np.ndarray:
    """Apply morphological opening to remove small stray pixels."""
    kernel = np.ones((kernel_size, kernel_size), np.uint8)
    return cv2.morphologyEx(image, cv2.MORPH_OPEN, kernel)


def dilate_image(image: np.ndarray, kernel_size: int = 2) -> np.ndarray:
    """Apply dilation to thicken characters."""
    kernel = np.ones((kernel_size, kernel_size), np.uint8)
    return cv2.dilate(image, kernel, iterations=1)


def clean_timer_region(image: np.ndarray, bg_color: int = 255) -> np.ndarray:
    """
    Remove the timer region in the bottom-right corner.
    Fills the area with the specified background color.
    """
    h, w = image.shape[:2]
    # Target the bottom right area roughly occupied by the timer icon
    start_y = int(h * 0.75)
    start_x = int(w * 0.88)
    
    result = image.copy()
    if len(result.shape) == 3:
        result[start_y:, start_x:] = (bg_color, bg_color, bg_color)
    else:
        result[start_y:, start_x:] = bg_color
    return result
