# Mock fcntl module for Windows compatibility
# This provides dummy implementations of fcntl functions

def fcntl(fd, cmd, arg=0):
    """Mock fcntl function"""
    return 0

def ioctl(fd, request, arg=0, mutate_flag=True):
    """Mock ioctl function"""
    return 0

def flock(fd, operation):
    """Mock flock function"""
    return 0

def lockf(fd, cmd, len=0, start=0, whence=0):
    """Mock lockf function"""
    return 0

# Constants that might be used
LOCK_SH = 1
LOCK_EX = 2
LOCK_NB = 4
LOCK_UN = 8

F_GETFL = 3
F_SETFL = 4
O_NONBLOCK = 2048
