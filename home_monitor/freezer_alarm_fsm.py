'''
Created on 21 Feb 2021

@author: keithgough
'''


class FreezerAlarm:
    """ Freezer Alarm Finite State Machine """
    def __init__(self, state):
        self.state = state

    def run(self):
        """ Run method """
        print(f"run {self.state}")


FM = FreezerAlarm('on')
