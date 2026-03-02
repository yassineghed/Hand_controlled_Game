import cv2
import numpy as np
import time

cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Cannot open camera")
    exit()

while True:
    ret, img = cap.read()

    if not ret:
        print("Failed to grab frame")
        break

    flipped_frame = cv2.flip(img, 1)
    cv2.imshow('Flipped Video', flipped_frame)

    if cv2.waitKey(1) & 0xFF == ord('b'):
        break

cap.release()
cv2.destroyAllWindows()