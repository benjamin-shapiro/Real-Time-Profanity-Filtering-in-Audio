import multiprocessing, ctypes

count = multiprocessing.Value(ctypes.c_int, 0)  # (type, init value)

def smile_detection(thread_name, count):

    for x in range(10):
        count.value +=1
        print (thread_name,count)

    return count    

if __name__ == "__main__":
    x = multiprocessing.Process(target=smile_detection, args=("Thread1", count))
    y = multiprocessing.Process(target=smile_detection, args=("Thread2", count))
    x.start()
    y.start()