#!/usr/bin/env python3

import rclpy.node
from azure_kinect_ros_msgs.msg import MarkerArrayStamped, ModelOutput
from sensor_msgs.msg import Image
from message_filters import ApproximateTimeSynchronizer, Subscriber
import numpy as np
from utils import image_to_numpy, numpy_to_image, Calibration, get_body_segments
import cv2
import matplotlib.cm as cm

class SkeletonToRGB(rclpy.node.Node):

    def __init__(self):
        super().__init__("skeleton_to_rgb")

        qos = rclpy.qos.QoSProfile(
            depth=1,
            # durability=rclpy.qos.QoSDurabilityPolicy.VOLATILE,
            # reliability=rclpy.qos.QoSReliabilityPolicy.BEST_EFFORT,
        )
        self.rgb_sub = Subscriber(self, Image, "/rgb/image_raw", qos_profile=qos)
        self.skeletons_sub = Subscriber(self, MarkerArrayStamped, "/body_tracking_data", qos_profile=qos)
        self.model_sub = Subscriber(self, ModelOutput,"model_output", qos_profile=qos)
        self.synchronizer = ApproximateTimeSynchronizer([self.rgb_sub, self.skeletons_sub, self.model_sub],
                                                        queue_size=1, slop=0.1)

        self.image_pub = self.create_publisher(Image, "/rgb/image_skeleton", 1)
        self.plot_bb = False
        self.synchronizer.registerCallback(self.topic_sync_cb)
        self.calibration = Calibration(2)
        self.get_logger().info("ready")
        
    def topic_sync_cb(self, rgb_msg, skeleton_msg, model_msg):
        image = image_to_numpy(rgb_msg)
        if len(skeleton_msg.markers) != 0:
            points_3d = np.array([[m.pose.position.x, m.pose.position.y, m.pose.position.z] for m in skeleton_msg.markers])
            points_3d *= 1000.
            points_2d = np.squeeze(self.calibration.depth_to_rgb_image(points_3d))
            points_2d = points_2d.astype(int).clip([0, 0], image.shape[1::-1])
            for body_s in range(0, len(points_2d), 32):
                body_id = skeleton_msg.markers[body_s].id //100
                proba = 0.
                for j, bid in enumerate(model_msg.ids):
                    if bid == body_id:
                        proba = model_msg.probas[j]
                        break
                color = [0, 255, 0]#[(body_id*10)%255]*3
                # color = (np.array(cm.viridis(proba))[:-1]*255) #[0, 255*label, 255*(not label)]#[(body_id*10)%255]*3
                # color = (int(color[2]), int(color[1]), int(color[0]))
                if self.plot_bb:
                    rect = cv2.boundingRect(points_2d[body_s:body_s+32])
                    image = cv2.rectangle(image, rect, color, 3)
                    image = cv2.putText(image, f"{proba:.2f}", (rect[0]+rect[2]-80, rect[1]+40), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 3)
                else:
                    for body_segment in get_body_segments():
                        for i in range(len(body_segment)-1):
                            image = cv2.line(image, 
                                            points_2d[body_s + body_segment[i]], 
                                            points_2d[body_s + body_segment[i+1]], 
                                            color, 2)
                    for point in points_2d[body_s:body_s+32]:
                        image = cv2.circle(image, point, 3, color, 3)
                        

        cv2.imshow('skeleton_rgb', image)
        cv2.waitKey(1)


def main(args=None):
    rclpy.init(args=args)
    node = SkeletonToRGB()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__=="__main__":
    main()