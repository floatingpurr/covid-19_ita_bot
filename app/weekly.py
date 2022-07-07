#!/usr/bin/env python
# -*- coding: utf-8 -*-


from utils.report import Report

def main():
    """Refresh data"""
    r = Report()
    r.notify_weekly()

if __name__ == '__main__':
    main()

