# -*- coding: utf-8 -*-

"""
helper functions for images
"""

from operator import itemgetter
from typing import List, Optional

import numpy

from mathics.builtin.base import String
from mathics.core.atoms import Rational
from mathics.core.convert.python import from_python
from mathics.core.evaluation import Evaluation
from mathics.core.expression import Expression
from mathics.core.list import ListExpression
from mathics.core.systemsymbols import SymbolRule, SymbolSimplify

try:
    from PIL.ExifTags import TAGS as ExifTags
except ImportError:
    ExifTags = {}

# Exif: Exchangeable image file format for digital still cameras.
# See http://www.exiv2.org/tags.html

# names overriding the ones given by Pillow
Exif_names = {
    37385: "FlashInfo",
    40960: "FlashpixVersion",
    40962: "PixelXDimension",
    40963: "PixelYDimension",
}


def convolve(in1, in2, fixed=True):
    """
    A very much boiled down version scipy.signal.signaltools.fftconvolve with added padding, see
    https://github.com/scipy/scipy/blob/master/scipy/signal/signaltools.py; please see the Scipy
    LICENSE in the accompanying files.
    """

    in1 = numpy.asarray(in1)
    in2 = numpy.asarray(in2)

    padding = numpy.array(in2.shape) // 2
    if fixed:  # add "Fixed" padding?
        in1 = numpy.pad(in1, padding, "edge")

    s1 = numpy.array(in1.shape)
    s2 = numpy.array(in2.shape)
    shape = s1 + s2 - 1

    sp1 = numpy.fft.rfftn(in1, shape)
    sp2 = numpy.fft.rfftn(in2, shape)
    ret = numpy.fft.irfftn(sp1 * sp2, shape)

    excess = (numpy.array(ret.shape) - s1) // 2 + padding
    return ret[tuple(slice(p, -p) for p in excess)]


def extract_exif(image, evaluation: Evaluation) -> Optional[Expression]:
    """
    Convert Exif information from image into options
    that can be passed to Image[].
    Return None if there is no Exif information.
    """
    if hasattr(image, "getexif"):

        # PIL seems to have a bug in getting v2_tags,
        # specifically tag offsets because
        # it expects image.fp to exist and for us it
        # doesn't.
        try:
            exif = image.getexif()
        except Exception:
            return None

        # If exif is None or an empty list, we have no information.
        if not exif:
            return None

        exif_options: List[Expression] = []

        for k, v in sorted(exif.items(), key=itemgetter(0)):
            name = ExifTags.get(k)
            if not name:
                continue

            # EXIF has the following types: Short, Long, Rational, Ascii, Byte
            # (see http://www.exiv2.org/tags.html). we detect the type from the
            # Python type Pillow gives us and do the appropiate MMA handling.

            if isinstance(v, tuple) and len(v) == 2:  # Rational
                value = Rational(v[0], v[1])
                if name == "FocalLength":
                    value = from_python(value.round(2))
                else:
                    value = Expression(SymbolSimplify, value).evaluate(evaluation)
            elif isinstance(v, bytes):  # Byte
                value = String(" ".join([str(x) for x in v]))
            elif isinstance(v, (int, str)):  # Short, Long, ASCII
                value = from_python(v)
            else:
                continue

            exif_options.append(
                Expression(SymbolRule, String(Exif_names.get(k, name)), value)
            )

        return Expression(SymbolRule, String("RawExif"), ListExpression(*exif_options))


def matrix_to_numpy(a):
    def matrix():
        for y in a.elements:
            yield [x.round_to_float() for x in y.elements]

    return numpy.array(list(matrix()))


def numpy_flip(pixels, axis):
    f = (numpy.flipud, numpy.fliplr)[axis]
    return f(pixels)


def numpy_to_matrix(pixels):
    channels = pixels.shape[2]
    if channels == 1:
        return pixels[:, :, 0].tolist()
    else:
        return pixels.tolist()


def pixels_as_float(pixels):
    dtype = pixels.dtype
    if dtype in (numpy.float32, numpy.float64):
        return pixels
    elif dtype == numpy.uint8:
        return pixels.astype(numpy.float32) / 255.0
    elif dtype == numpy.uint16:
        return pixels.astype(numpy.float32) / 65535.0
    elif dtype is numpy.dtype(bool):
        return pixels.astype(numpy.float32)
    else:
        raise NotImplementedError


def pixels_as_ubyte(pixels):
    dtype = pixels.dtype
    if dtype in (numpy.float32, numpy.float64):
        pixels = numpy.maximum(numpy.minimum(pixels, 1.0), 0.0)
        return (pixels * 255.0).astype(numpy.uint8)
    elif dtype == numpy.uint8:
        return pixels
    elif dtype == numpy.uint16:
        return (pixels / 256).astype(numpy.uint8)
    elif dtype is numpy.dtype(bool):
        return pixels.astype(numpy.uint8) * 255
    else:
        raise NotImplementedError


def pixels_as_uint(pixels):
    dtype = pixels.dtype
    if dtype in (numpy.float32, numpy.float64):
        pixels = numpy.maximum(numpy.minimum(pixels, 1.0), 0.0)
        return (pixels * 65535.0).astype(numpy.uint16)
    elif dtype == numpy.uint8:
        return pixels.astype(numpy.uint16) * 256
    elif dtype == numpy.uint16:
        return pixels
    elif dtype is numpy.dtype(bool):
        return pixels.astype(numpy.uint8) * 65535
    else:
        raise NotImplementedError
