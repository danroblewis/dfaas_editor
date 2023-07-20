from dfaal import parse_applications
import os

for fname in os.listdir('./examples/'):
    print("=-=-=--=-=-=-", fname)
    try:
        with open('./examples/' + fname) as f:
            t = f.read()
            p = parse_applications(t)
            print(p)
    except Exception as e:
        print(e)
