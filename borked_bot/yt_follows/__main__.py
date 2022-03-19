import argparse
import os

parser = argparse.ArgumentParser(description='Update youtube follow count data.')
parser.add_argument('--all_items', action='store_true')
parser.add_argument('--enwiki', action='store_true')

args = parser.parse_args()

if __name__ == '__main__':
    if args.all_items:
        os.environ['ALL_ITEMS'] = "1"
    if args.enwiki:
        os.environ['ENWIKI'] = "1"
    from . import run

