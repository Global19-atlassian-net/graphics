#Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""This module implements math routines used by OpenGL."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import math
import tensorflow as tf

from tensorflow_graphics.math import vector
from tensorflow_graphics.util import asserts
from tensorflow_graphics.util import export_api
from tensorflow_graphics.util import shape


def perspective_right_handed(vertical_field_of_view,
                             aspect_ratio,
                             near,
                             far,
                             name=None):
  """Generates the matrix for a right handed perspective projection.

  Note:
    In the following, A1 to An are optional batch dimensions.

  Args:
    vertical_field_of_view: A tensor of shape `[A1, ..., An, C]`, where the last
      dimension represents the vertical field of view of the frustum expressed
      in radians. Note that values for `vertical_field_of_view` must be in the
      range (0,pi).
    aspect_ratio: A tensor of shape `[A1, ..., An, C]`, where the last dimension
      stores the width over height ratio of the frustum. Note that values for
      `aspect_ratio` must be non-negative.
    near:  A tensor of shape `[A1, ..., An, C]`, where the last dimension
      captures the distance between the viewer and the near clipping plane. Note
      that values for `near` must be non-negative.
    far:  A tensor of shape `[A1, ..., An, C]`, where the last dimension
      captures the distance between the viewer and the far clipping plane. Note
      that values for `far` must be greater than those of `near`.
    name: A name for this op. Defaults to 'perspective_rh'.

  Raises:
    InvalidArgumentError: if any input contains data not in the specified range
      of valid values.
    ValueError: if the all the inputs are not of the same shape.

  Returns:
    A tensor of shape `[A1, ..., An, 4, 4]`, containing matrices of right
    handed perspective-view frustum.
  """
  with tf.compat.v1.name_scope(
      name, "perspective_rh",
      [vertical_field_of_view, aspect_ratio, near, far]):
    vertical_field_of_view = tf.convert_to_tensor(value=vertical_field_of_view)
    aspect_ratio = tf.convert_to_tensor(value=aspect_ratio)
    near = tf.convert_to_tensor(value=near)
    far = tf.convert_to_tensor(value=far)

    shape.compare_batch_dimensions(
        tensors=(vertical_field_of_view, aspect_ratio, near, far),
        last_axes=-1,
        tensor_names=("vertical_field_of_view", "aspect_ratio", "near", "far"),
        broadcast_compatible=False)

    vertical_field_of_view = asserts.assert_all_in_range(
        vertical_field_of_view, 0.0, math.pi, open_bounds=True)
    aspect_ratio = asserts.assert_all_above(aspect_ratio, 0.0, open_bound=True)
    near = asserts.assert_all_above(near, 0.0, open_bound=True)
    far = asserts.assert_all_above(far, near, open_bound=True)

    inverse_tan_half_vertical_field_of_view = 1.0 / tf.tan(
        vertical_field_of_view * 0.5)
    zero = tf.zeros_like(inverse_tan_half_vertical_field_of_view)
    one = tf.ones_like(inverse_tan_half_vertical_field_of_view)

    x = tf.stack((inverse_tan_half_vertical_field_of_view / aspect_ratio, zero,
                  zero, zero),
                 axis=-1)
    y = tf.stack((zero, inverse_tan_half_vertical_field_of_view, zero, zero),
                 axis=-1)
    near_minus_far = near - far
    z = tf.stack(
        (zero, zero,
         (far + near) / near_minus_far, 2.0 * far * near / near_minus_far),
        axis=-1)
    w = tf.stack((zero, zero, -one, zero), axis=-1)
    return tf.stack((x, y, z, w), axis=-2)


def look_at_right_handed(camera_position, look_at, up_vector, name=None):
  """Builds a right handed look at view matrix.

  Note:
    In the following, A1 to An are optional batch dimensions.

  Args:
    camera_position: A tensor of shape `[A1, ..., An, 3]`, where the last
      dimension represents the 3D position of the camera.
    look_at: A tensor of shape `[A1, ..., An, 3]`, with the last dimension
      storing the position where the camera is looking at.
    up_vector: A tensor of shape `[A1, ..., An, 3]`, where the last dimension
      defines the up vector of the camera.
    name: A name for this op. Defaults to 'look_at_right_handed'.

  Raises:
    ValueError: if the all the inputs are not of the same shape, or if any input
    of of an unsupported shape.

  Returns:
    A tensor of shape `[A1, ..., An, 4, 4]`, containing right handed look at
    matrices.
  """
  with tf.compat.v1.name_scope(name, "look_at_right_handed",
                               [camera_position, look_at, up_vector]):
    camera_position = tf.convert_to_tensor(value=camera_position)
    look_at = tf.convert_to_tensor(value=look_at)
    up_vector = tf.convert_to_tensor(value=up_vector)

    shape.check_static(
        tensor=camera_position,
        tensor_name="camera_position",
        has_dim_equals=(-1, 3))
    shape.check_static(
        tensor=look_at, tensor_name="look_at", has_dim_equals=(-1, 3))
    shape.check_static(
        tensor=up_vector, tensor_name="up_vector", has_dim_equals=(-1, 3))
    shape.compare_batch_dimensions(
        tensors=(camera_position, look_at, up_vector),
        last_axes=-2,
        tensor_names=("camera_position", "look_at", "up_vector"),
        broadcast_compatible=False)

    z_axis = tf.linalg.l2_normalize(look_at - camera_position, axis=-1)
    horizontal_axis = tf.linalg.l2_normalize(
        vector.cross(z_axis, up_vector), axis=-1)
    vertical_axis = vector.cross(horizontal_axis, z_axis)

    batch_shape = tf.shape(input=horizontal_axis)[:-1]
    zeros = tf.zeros(
        shape=tf.concat((batch_shape, (3,)), axis=-1),
        dtype=horizontal_axis.dtype)
    one = tf.ones(
        shape=tf.concat((batch_shape, (1,)), axis=-1),
        dtype=horizontal_axis.dtype)
    x = tf.concat(
        (horizontal_axis, -vector.dot(horizontal_axis, camera_position)),
        axis=-1)
    y = tf.concat((vertical_axis, -vector.dot(vertical_axis, camera_position)),
                  axis=-1)
    z = tf.concat((-z_axis, vector.dot(z_axis, camera_position)), axis=-1)
    w = tf.concat((zeros, one), axis=-1)
    return tf.stack((x, y, z, w), axis=-2)


def model_to_eye(point_model_space,
                 camera_position,
                 look_at,
                 up_vector,
                 name=None):
  """Transforms points from model to eye coordinates.

  Note:
    In the following, A1 to An are optional batch dimensions which must be
    broadcast compatible.

  Args:
    point_model_space: A tensor of shape `[A1, ..., An, 3]`, where the last
      dimension represents the 3D points in model space.
    camera_position: A tensor of shape `[A1, ..., An, 3]`, where the last
      dimension represents the 3D position of the camera.
    look_at: A tensor of shape `[A1, ..., An, 3]`, with the last dimension
      storing the position where the camera is looking at.
    up_vector: A tensor of shape `[A1, ..., An, 3]`, where the last dimension
      defines the up vector of the camera.
    name: A name for this op. Defaults to 'model_to_eye'.

  Raises:
    ValueError: if the all the inputs are not of the same shape, or if any input
    of of an unsupported shape.

  Returns:
    A tensor of shape `[A1, ..., An, 3]`, containing `point_model_space` in eye
    coordinates.
  """
  with tf.compat.v1.name_scope(
      name, "model_to_eye",
      [point_model_space, camera_position, look_at, up_vector]):
    point_model_space = tf.convert_to_tensor(value=point_model_space)
    camera_position = tf.convert_to_tensor(value=camera_position)
    look_at = tf.convert_to_tensor(value=look_at)
    up_vector = tf.convert_to_tensor(value=up_vector)

    shape.check_static(
        tensor=point_model_space,
        tensor_name="point_model_space",
        has_dim_equals=(-1, 3))
    shape.compare_batch_dimensions(
        tensors=(point_model_space, camera_position, look_at, up_vector),
        last_axes=-2,
        tensor_names=("point_model_space", "camera_position", "look_at",
                      "up_vector"),
        broadcast_compatible=True)

    model_to_eye_matrix = look_at_right_handed(camera_position, look_at,
                                               up_vector)
    batch_shape = tf.shape(input=point_model_space)[:-1]
    one = tf.ones(
        shape=tf.concat((batch_shape, (1,)), axis=-1),
        dtype=point_model_space.dtype)
    point_model_space = tf.concat((point_model_space, one), axis=-1)
    point_model_space = tf.expand_dims(point_model_space, axis=-1)
    res = tf.squeeze(tf.matmul(model_to_eye_matrix, point_model_space), axis=-1)
    return res[..., :-1]


def eye_to_clip(point_eye_space,
                vertical_field_of_view,
                aspect_ratio,
                near,
                far,
                name=None):
  """Transforms points from eye to clip space.

  Note:
    In the following, A1 to An are optional batch dimensions.

  Args:
    point_eye_space: A tensor of shape `[A1, ..., An, 3]`, where the last
      dimension represents the 3D points in eye coordinates.
    vertical_field_of_view: A tensor of shape `[A1, ..., An, 1]`, where the last
      dimension represents the vertical field of view of the frustum. Note that
      values for `vertical_field_of_view` must be in the range ]0,pi[.
    aspect_ratio: A tensor of shape `[A1, ..., An, 1]`, where the last dimension
      stores the width over height ratio of the frustum. Note that values for
      `aspect_ratio` must be non-negative.
    near: A tensor of shape `[A1, ..., An, 1]`, where the last dimension
      captures the distance between the viewer and the near clipping plane. Note
      that values for `near` must be non-negative.
    far: A tensor of shape `[A1, ..., An, 1]`, where the last dimension captures
      the distance between the viewer and the far clipping plane. Note that
      values for `far` must be non-negative.
    name: A name for this op. Defaults to 'eye_to_clip'.

  Raises:
    ValueError: If any input is of an unsupported shape.

  Returns:
    A tensor of shape `[A1, ..., An, 4]`, containing `point_eye_space` in
    homogeneous clip coordinates.
  """
  with tf.compat.v1.name_scope(
      name, "eye_to_clip",
      [point_eye_space, vertical_field_of_view, aspect_ratio, near, far]):
    point_eye_space = tf.convert_to_tensor(value=point_eye_space)
    vertical_field_of_view = tf.convert_to_tensor(value=vertical_field_of_view)
    aspect_ratio = tf.convert_to_tensor(value=aspect_ratio)
    near = tf.convert_to_tensor(value=near)
    far = tf.convert_to_tensor(value=far)

    shape.check_static(
        tensor=point_eye_space,
        tensor_name="point_eye_space",
        has_dim_equals=(-1, 3))
    shape.check_static(
        tensor=vertical_field_of_view,
        tensor_name="vertical_field_of_view",
        has_dim_equals=(-1, 1))
    shape.check_static(
        tensor=aspect_ratio, tensor_name="aspect_ratio", has_dim_equals=(-1, 1))
    shape.check_static(tensor=near, tensor_name="near", has_dim_equals=(-1, 1))
    shape.check_static(tensor=far, tensor_name="far", has_dim_equals=(-1, 1))
    shape.compare_batch_dimensions(
        tensors=(point_eye_space, vertical_field_of_view, aspect_ratio, near,
                 far),
        last_axes=-2,
        tensor_names=("point_eye_space", "vertical_field_of_view",
                      "aspect_ratio", "near", "far"),
        broadcast_compatible=True)

    perspective_matrix = perspective_right_handed(vertical_field_of_view,
                                                  aspect_ratio, near, far)
    perspective_matrix = tf.squeeze(perspective_matrix, axis=-3)
    batch_shape = tf.shape(input=point_eye_space)[:-1]
    one = tf.ones(
        shape=tf.concat((batch_shape, (1,)), axis=-1),
        dtype=point_eye_space.dtype)
    point_eye_space = tf.concat((point_eye_space, one), axis=-1)
    point_eye_space = tf.expand_dims(point_eye_space, axis=-1)

    return tf.squeeze(tf.matmul(perspective_matrix, point_eye_space), axis=-1)


def clip_to_ndc(point_clip_space, name=None):
  """Transforms points from clip to normalized device coordinates (ndc).

  Note:
    In the following, A1 to An are optional batch dimensions.

  Args:
    point_clip_space: A tensor of shape `[A1, ..., An, 4]`, where the last
      dimension represents points in clip space.
    name: A name for this op. Defaults to 'clip_to_ndc'.

  Raises:
    ValueError: If `point_clip_space` is not of size 4 in its last dimension.

  Returns:
    A tensor of shape `[A1, ..., An, 3]`, containing `point_clip_space` in
    normalized device coordinates.
  """
  with tf.compat.v1.name_scope(name, "clip_to_ndc", [point_clip_space]):
    point_clip_space = tf.convert_to_tensor(value=point_clip_space)

    shape.check_static(
        tensor=point_clip_space,
        tensor_name="point_clip_space",
        has_dim_equals=(-1, 4))

    w = point_clip_space[..., -1:]
    return point_clip_space[..., :3] / w

# API contains all public functions and classes.
__all__ = export_api.get_functions_and_classes()
