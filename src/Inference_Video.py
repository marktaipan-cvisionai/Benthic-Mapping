import os.path
import argparse
from tqdm import tqdm

import numpy as np

import supervision as sv
from ultralytics import YOLO

from Auto_Distill import filter_detections


# ----------------------------------------------------------------------------------------------------------------------
# Functions
# ----------------------------------------------------------------------------------------------------------------------


def process_video(source_weights, source_video, output_dir, task, start_at, end_at, conf=.3, iou=.7):
    """

    :param source_weights:
    :param source_video:
    :param output_dir:
    :param start_art:
    :param end_at:
    :param conf:
    :param iou:
    :return:
    """
    # Create the target path
    target_video_path = f"{output_dir}/{os.path.basename(source_video)}"
    # Create the target directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Load the model
    model = YOLO(source_weights)

    # If user didn't specify the task, use
    # the one that the model was trained for
    if not args.task:
        task = model.ckpt['model'].task

    if task == 'detect':
        # Load the tracker
        tracker = sv.ByteTrack()
        # Create the annotator for detection
        box_annotator = sv.BoundingBoxAnnotator()
        # Adds label to annotation (tracking)
        label_annotator = sv.LabelAnnotator()
    else:
        # Create the annotators for segmentation
        mask_annotator = sv.MaskAnnotator()
        box_annotator = sv.BoundingBoxAnnotator()

    # Create the video generators
    frame_generator = sv.get_video_frames_generator(source_path=source_video)
    video_info = sv.VideoInfo.from_video_path(video_path=source_video)

    # Where to start and end inference
    if start_at <= 0:
        start_at = 0
    if end_at <= -1:
        end_at = video_info.total_frames

    # Frame count
    f_idx = 0

    # Loop through all the frames
    with sv.VideoSink(target_path=target_video_path, video_info=video_info) as sink:
        for frame in tqdm(frame_generator, total=video_info.total_frames):

            if start_at < f_idx < end_at:

                # Run the frame through the model
                result = model(frame, verbose=False, conf=conf, iou=iou, imgsz=1280)[0]
                result.obb = None

                # Convert the results
                detections = sv.Detections.from_ultralytics(result)

                # Filter the detections
                indicies = filter_detections(frame, detections, area_threshold=0.40)
                detections = detections[indicies]

                if task == 'detect':
                    # Track the detections
                    detections = tracker.update_with_detections(detections)
                    labels = [f"#{tracker_id}" for tracker_id in detections.tracker_id]
                    # Create an annotated version of the frame (boxes)
                    annotated_frame = box_annotator.annotate(scene=frame.copy(), detections=detections)
                    # Add tracking IDs
                    annotated_frame = label_annotator.annotate(scene=annotated_frame,
                                                               detections=detections,
                                                               labels=labels)
                else:
                    # Create an annotated version of the frame (masks and boxes)
                    annotated_frame = mask_annotator.annotate(scene=frame.copy(), detections=detections)
                    annotated_frame = box_annotator.annotate(scene=annotated_frame.copy(), detections=detections)

                # Write the frame to the video
                sink.write_frame(frame=annotated_frame)

            else:
                sink.write_frame(frame)

            f_idx += 1


# ----------------------------------------------------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Video Processing with YOLO and ByteTrack")

    parser.add_argument(
        "--source_weights",
        required=True,
        help="Path to the source weights file",
        type=str,
    )
    parser.add_argument(
        "--source_video",
        required=True,
        help="Path to the source video file",
        type=str,
    )
    parser.add_argument(
        "--output_dir",
        required=True,
        help="Path to the target video directory (output)",
        type=str,
    )
    parser.add_argument(
        "--task",
        help="Override the model's task to perform "
             "detections or segmentations (if applicable)",
        type=str,
    )
    parser.add_argument(
        "--start_at",
        default=0,
        help="Frame to start inference",
        type=int,
    )
    parser.add_argument(
        "--end_at",
        default=-1,
        help="Frame to end inference",
        type=int,
    )
    parser.add_argument(
        "--conf",
        default=0.50,
        help="Confidence threshold for the model",
        type=float,
    )
    parser.add_argument(
        "--iou", default=0.5, help="IOU threshold for the model", type=float
    )

    args = parser.parse_args()

    process_video(
        source_weights=args.source_weights,
        source_video=args.source_video,
        output_dir=args.output_dir,
        task=args.task,
        start_at=args.start_at,
        end_at=args.end_at,
        conf=args.conf,
        iou=args.iou,
    )