"""
Motion Detection untuk mendeteksi kendaraan cepat yang terlewatkan oleh frame-to-frame.

Menggunakan optical flow dan frame differencing untuk menangkap gerakan objek cepat
yang mungkin tidak terdeteksi oleh YOLO saja (karena skip frame atau motion blur).
"""

import cv2
import numpy as np


class MotionDetector:
    """
    Deteksi gerakan antar frame untuk menangkap kendaraan cepat.
    Menggabungkan frame differencing dan optical flow.
    """
    
    def __init__(self, sensitivity=0.3, min_area=500, max_area=500000):
        """
        Args:
            sensitivity: Threshold gerakan (0.0-1.0). Lebih rendah = lebih sensitif
            min_area: Ukuran minimum area gerakan (pixel^2)
            max_area: Ukuran maksimum area gerakan (pixel^2)
        """
        self.sensitivity = sensitivity
        self.min_area = min_area
        self.max_area = max_area
        self.prev_gray = None
        self.prev_frame = None
        
    def detect_motion(self, frame):
        """
        Deteksi area gerakan dalam frame saat ini vs frame sebelumnya.
        
        Returns:
            - motion_regions: list[tuple] = [(x1, y1, x2, y2), ...] bounding box gerakan
            - motion_mask: np.ndarray = binary mask area gerakan
            - motion_score: float = skor gerakan keseluruhan (0.0-1.0)
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        
        motion_regions = []
        motion_mask = np.zeros((h, w), dtype=np.uint8)
        motion_score = 0.0
        
        if self.prev_gray is None:
            self.prev_gray = gray
            self.prev_frame = frame
            return motion_regions, motion_mask, motion_score
        
        # ─── Method 1: Frame Differencing ─────────────────────────────────
        frame_diff = cv2.absdiff(self.prev_gray, gray)
        
        # Gaussian blur untuk reduce noise
        frame_diff = cv2.GaussianBlur(frame_diff, (5, 5), 0)
        
        # Threshold untuk detect motion
        threshold = int(255 * self.sensitivity)
        _, motion_mask_diff = cv2.threshold(frame_diff, threshold, 255, cv2.THRESH_BINARY)
        
        # Morphological operations untuk clean up
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        motion_mask_diff = cv2.morphologyEx(motion_mask_diff, cv2.MORPH_CLOSE, kernel)
        motion_mask_diff = cv2.morphologyEx(motion_mask_diff, cv2.MORPH_OPEN, kernel)
        
        # ─── Method 2: Optical Flow (Lucas-Kanade) ────────────────────────
        # Detect corners untuk optical flow tracking
        corners = cv2.goodFeaturesToTrack(
            self.prev_gray,
            maxCorners=500,
            qualityLevel=0.01,
            minDistance=10
        )
        
        motion_mask_flow = np.zeros((h, w), dtype=np.uint8)
        
        if corners is not None:
            corners = np.float32(corners)
            
            # Calculate optical flow using Pyramidal Lucas-Kanade
            flow, status, err = cv2.calcOpticalFlowPyrLK(
                self.prev_gray, gray,
                corners,
                None,
                winSize=(15, 15),
                maxLevel=3,
                criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03)
            )
            
            # Gambar optical flow sebagai mask
            if status is not None:
                good_old = corners[status == 1]
                good_new = flow[status == 1]
                
                for (old_x, old_y), (new_x, new_y) in zip(good_old, good_new):
                    x, y = int(old_x), int(old_y)
                    dx, dy = int(new_x - old_x), int(new_y - old_y)
                    
                    # Highlight area dengan movement
                    if (dx**2 + dy**2) > 5:  # Ada gerakan signifikan
                        cv2.circle(motion_mask_flow, (x, y), 15, 255, -1)
        
        # ─── Combine kedua method ─────────────────────────────────────────
        motion_mask = cv2.bitwise_or(motion_mask_diff, motion_mask_flow)
        
        # ─── Ekstrak bounding boxes dari motion regions ────────────────────
        contours, _ = cv2.findContours(motion_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            area = cv2.contourArea(contour)
            
            if self.min_area <= area <= self.max_area:
                x, y, w, h = cv2.boundingRect(contour)
                motion_regions.append((x, y, x + w, y + h))
        
        # Calculate overall motion score
        motion_score = np.sum(motion_mask) / (h * w * 255)
        
        self.prev_gray = gray
        self.prev_frame = frame
        
        return motion_regions, motion_mask, motion_score
    
    
    def get_combined_detections(self, yolo_boxes, motion_regions):
        """
        Combine YOLO detections dengan motion-detected regions.
        Kendaraan cepat yang terlewat YOLO mungkin terdeteksi dari motion.
        
        Args:
            yolo_boxes: list[(x1, y1, x2, y2, conf), ...] dari YOLO
            motion_regions: list[(x1, y1, x2, y2), ...] dari motion detection
        
        Returns:
            - combined: list[(x1, y1, x2, y2, conf, source), ...] 
              source = 'yolo' atau 'motion'
            - new_detections: list[(x1, y1, x2, y2), ...] motion-only detections
        """
        combined = []
        covered_motion = set()
        
        # Add YOLO detections
        for i, (x1, y1, x2, y2, conf) in enumerate(yolo_boxes):
            combined.append((x1, y1, x2, y2, conf, 'yolo'))
        
        # Check motion regions yang tidak covered oleh YOLO
        new_detections = []
        
        for j, (mx1, my1, mx2, my2) in enumerate(motion_regions):
            # Check apakah motion region overlap dengan YOLO box
            overlap = False
            
            for (yx1, yy1, yx2, yy2, _, _) in combined:
                # Calculate IoU
                iou = _calculate_iou(
                    (yx1, yy1, yx2, yy2),
                    (mx1, my1, mx2, my2)
                )
                if iou > 0.3:  # Ada overlap signifikan
                    overlap = True
                    break
            
            if not overlap:
                # Motion region ini adalah deteksi baru (kendaraan cepat yang terlewat)
                new_detections.append((mx1, my1, mx2, my2))
                combined.append((mx1, my1, mx2, my2, 0.5, 'motion'))
                covered_motion.add(j)
        
        return combined, new_detections


def _calculate_iou(box1, box2):
    """Calculate Intersection over Union."""
    x1_1, y1_1, x2_1, y2_1 = box1
    x1_2, y1_2, x2_2, y2_2 = box2
    
    # Intersection
    xi1 = max(x1_1, x1_2)
    yi1 = max(y1_1, y1_2)
    xi2 = min(x2_1, x2_2)
    yi2 = min(y2_1, y2_2)
    
    inter_area = max(0, xi2 - xi1) * max(0, yi2 - yi1)
    
    # Union
    box1_area = (x2_1 - x1_1) * (y2_1 - y1_1)
    box2_area = (x2_2 - x1_2) * (y2_2 - y1_2)
    union_area = box1_area + box2_area - inter_area
    
    if union_area == 0:
        return 0.0
    
    return inter_area / union_area
