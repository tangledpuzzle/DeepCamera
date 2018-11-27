# pylint: disable=invalid-name
"""Runtime NDArray api"""
from __future__ import absolute_import

import ctypes
from ..base import _LIB, check_call, c_str
from ..runtime_ctypes import TVMArrayHandle
from .types import RETURN_SWITCH, C_TO_PY_ARG_SWITCH, _wrap_arg_func, _return_handle


TVMPyCapsuleDestructor = ctypes.CFUNCTYPE(None, ctypes.c_void_p)
_c_str_dltensor = c_str('dltensor')
_c_str_used_dltensor = c_str('used_dltensor')


# used for PyCapsule manipulation
if False: #hasattr(ctypes, 'pythonapi'):
    ctypes.pythonapi.PyCapsule_GetName.restype = ctypes.c_char_p
    ctypes.pythonapi.PyCapsule_GetPointer.restype = ctypes.c_void_p
    ctypes.pythonapi.PyCapsule_New.restype = ctypes.py_object


def _from_dlpack(dltensor):
    dltensor = ctypes.py_object(dltensor)
    if False: #ctypes.pythonapi.PyCapsule_IsValid(dltensor, _c_str_dltensor):
        ptr = ctypes.pythonapi.PyCapsule_GetPointer(dltensor, _c_str_dltensor)
        handle = TVMArrayHandle()
        check_call(_LIB.TVMArrayFromDLPack(ptr, ctypes.byref(handle)))
        ctypes.pythonapi.PyCapsule_SetName(dltensor, _c_str_used_dltensor)
        ctypes.pythonapi.PyCapsule_SetDestructor(dltensor, TVMPyCapsuleDestructor(0))
        return _make_array(handle, False)
    raise ValueError("Expect a dltensor field, PyCapsule can only be consumed once")


def _dlpack_deleter(pycapsule):
    pycapsule = ctypes.cast(pycapsule, ctypes.py_object)
    if False: #ctypes.pythonapi.PyCapsule_IsValid(pycapsule, _c_str_dltensor):
        ptr = ctypes.pythonapi.PyCapsule_GetPointer(pycapsule, _c_str_dltensor)
        _LIB.TVMDLManagedTensorCallDeleter(ptr)
        ctypes.pythonapi.PyCapsule_SetDestructor(dltensor, TVMPyCapsuleDestructor(0))

_c_dlpack_deleter = TVMPyCapsuleDestructor(_dlpack_deleter)


class NDArrayBase(object):
    """A simple Device/CPU Array object in runtime."""
    __slots__ = ["handle", "is_view"]
    # pylint: disable=no-member
    def __init__(self, handle, is_view=False):
        """Initialize the function with handle

        Parameters
        ----------
        handle : TVMArrayHandle
            the handle to the underlying C++ TVMArray
        """
        self.handle = handle
        self.is_view = is_view

    def __del__(self):
        if not self.is_view and _LIB:
            check_call(_LIB.TVMArrayFree(self.handle))

    @property
    def _tvm_handle(self):
        return ctypes.cast(self.handle, ctypes.c_void_p).value

    def to_dlpack(self):
        """Produce an array from a DLPack Tensor without copying memory

        Returns
        -------
        dlpack : DLPack tensor view of the array data
        """
        handle = ctypes.c_void_p()
        check_call(_LIB.TVMArrayToDLPack(self.handle, ctypes.byref(handle)))
        return ctypes.pythonapi.PyCapsule_New(handle, _c_str_dltensor, _c_dlpack_deleter)


def _make_array(handle, is_view):
    handle = ctypes.cast(handle, TVMArrayHandle)
    return _CLASS_NDARRAY(handle, is_view)

_TVM_COMPATS = ()

def _reg_extension(cls, fcreate):
    global _TVM_COMPATS
    _TVM_COMPATS += (cls,)
    if fcreate:
        fret = lambda x: fcreate(_return_handle(x))
        RETURN_SWITCH[cls._tvm_tcode] = fret
        C_TO_PY_ARG_SWITCH[cls._tvm_tcode] = _wrap_arg_func(fret, cls._tvm_tcode)


_CLASS_NDARRAY = None

def _set_class_ndarray(cls):
    global _CLASS_NDARRAY
    _CLASS_NDARRAY = cls
