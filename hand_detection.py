import numpy as np
import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import numpy as np

HAND_CONNECTIONS = [
    (0,1),(1,2),(2,3),(3,4),       # Thumb
    (0,5),(5,6),(6,7),(7,8),       # Index
    (5,9),(9,10),(10,11),(11,12),  # Middle
    (9,13),(13,14),(14,15),(15,16),# Ring
    (13,17),(17,18),(18,19),(19,20),# Pinky
    (0,17)                          # Palm
]

FINGER_COLORS = [
    (0, 0, 255),    # Thumb - Red
    (0, 165, 255),  # Index - Orange
    (0, 255, 0),    # Middle - Green
    (255, 0, 0),    # Ring - Blue
    (255, 0, 255),  # Pinky - Purple
]

FINGER_RANGES = [(0,4),(5,8),(9,12),(13,16),(17,20)]

def get_finger_color(start):
    for i, (s, e) in enumerate(FINGER_RANGES):
        if s <= start <= e:
            return FINGER_COLORS[i]
    return (255, 255, 255)

def draw_landmarks(image, detection_result):
    h, w, _ = image.shape

    for idx, hand_landmarks in enumerate(detection_result.hand_landmarks):
        # Determine handedness label
        if detection_result.handedness and idx < len(detection_result.handedness):
            label = detection_result.handedness[idx][0].display_name
        else:
            label = f"Hand {idx+1}"

        # Draw connections
        for start, end in HAND_CONNECTIONS:
            x0 = int(hand_landmarks[start].x * w)
            y0 = int(hand_landmarks[start].y * h)
            x1 = int(hand_landmarks[end].x * w)
            y1 = int(hand_landmarks[end].y * h)
            color = get_finger_color(start)
            cv2.line(image, (x0, y0), (x1, y1), color, 2)

        # Draw landmark dots
        for lm in hand_landmarks:
            cx, cy = int(lm.x * w), int(lm.y * h)
            cv2.circle(image, (cx, cy), 5, (0,0,0), -1)
            cv2.circle(image, (cx, cy), 5, (0, 0, 0), 1)

        # Draw label near wrist
        wrist = hand_landmarks[0]
        wx, wy = int(wrist.x * w), int(wrist.y * h)
        cv2.putText(image, label, (wx - 30, wy + 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)

    return image

# Load model
base_options = python.BaseOptions(
    model_asset_path=r'C:\Users\pc\Documents\ML\Hand_controlled_game\hand_landmarker.task'
)
options = vision.HandLandmarkerOptions(
    base_options=base_options,
    num_hands=2,                          # Detect up to 2 hands
    min_hand_detection_confidence=0.4,
    min_hand_presence_confidence=0.4,
    min_tracking_confidence=0.2
)

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

print("Hand detection started. Press ESC to quit.")

with vision.HandLandmarker.create_from_options(options) as landmarker:
    while cap.isOpened():
        success, frame = cap.read()
        if not success:
            continue

        frame = cv2.flip(frame, 1)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        result = landmarker.detect(mp_image)

        # Show hand count on screen
        hand_count = len(result.hand_landmarks)
        annotated = draw_landmarks(rgb_frame.copy(), result)
        output = cv2.cvtColor(annotated, cv2.COLOR_RGB2BGR)

        cv2.putText(output, f'Score : {hand_count}', (10, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 3, (245, 245, 245), 4)
        
        cv2.imshow('Hand Detection', output)
        if cv2.waitKey(5) & 0xFF == 27:
            break

cap.release()
cv2.destroyAllWindows()