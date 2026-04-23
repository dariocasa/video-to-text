from __future__ import annotations

import numpy as np
from app.ocr.detector import find_horizontal_split
from app.ocr.preprocessors import (
    apply_threshold,
    clean_timer_region,
    denoise_image,
    dilate_image,
    invert_colors,
    morph_open,
    scale_image,
    to_grayscale,
)


class QuizFrameProcessor:
    """Orchestrates image splitting and specialized preprocessing for quiz frames."""

    @staticmethod
    def process(image: np.ndarray, filename: str) -> list[tuple[np.ndarray, str]]:
        """
        Split the frame and return a list of (preprocessed_image, label) tuples.
        """
        is_answer_frame = "_answer" in filename.lower()
        split_y = find_horizontal_split(image)
        margin = 5  # Small safety margin for the header

        header_img = image[: split_y - margin, :]
        body_img = image[split_y:, :]

        # 1. Process Header (Question or Answer)
        # Questions (First frame) are white-on-dark. We use a more aggressive
        # cleaning pipeline to remove compression artifacts and noise.
        header_gray = to_grayscale(header_img)
        if not is_answer_frame:
            header_inverted = invert_colors(header_gray)
            header_denoised = denoise_image(header_inverted)
            header_binary = apply_threshold(header_denoised)
            header_dilated = dilate_image(header_binary, kernel_size=2)
            header_final = scale_image(header_dilated, 2.0)
        else:
            # Answers are already dark-on-light green.
            # We apply thresholding and dilation to make the text sharper.
            header_binary = apply_threshold(header_gray)
            header_dilated = dilate_image(header_binary, kernel_size=2)
            header_final = scale_image(header_dilated, 2.0)

        # 2. Process Body (Options or Explanation)
        # Both are dark-on-light. Remove the timer first.
        body_clean = clean_timer_region(body_img)
        body_gray = to_grayscale(body_clean)
        body_binary = apply_threshold(body_gray)
        body_final = scale_image(body_binary, 2.0)

        if is_answer_frame:
            return [
                (header_final, "answer"),
                (body_final, "explanation"),
            ]
        else:
            return [
                (header_final, "question"),
                (body_final, "option"),
            ]
