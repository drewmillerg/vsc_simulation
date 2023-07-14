"""Simulates call center where customer interactions are coming in over 
    24 hours

    To Do: 
    change the time increments from minutes to seconds
    record measurements for asr and so on
    have customer interactions come in over a norm dist
"""

import random
import simpy
import numpy as np
import pandas as pd
import datetime
import csv

# in seconds (480 sec = 8 min) 10.6min = 640 sec, effective handle time, 
#   based on 45 interaction per agent. This was the average as of 2/8/23 with
#   our heaviest volumes
HANDLE_TIME = int(np.random.normal(579, 5, 1)) 
# number of interactions that will come in through the day
NUM_INTERACTIONS = int(np.random.normal(835, 4, 1))
NUM_AGENTS = 15
SHIFT_LENGTH = 8
DAY_LENGTH = 24

MEAN_AGENT_START_TIME = 8
AGENT_START_STDEV = 3

CURRENT_DAY = 0

def pick(env, queue, ident):
    while True:
        try:
            order = yield queue.get()
        except simpy.Interrupt:
            break
        else:
            print(f'Agent {ident} began order at {get_time(env)}')

        start_time = env.now
        try:
            yield env.timeout(HANDLE_TIME)
        except simpy.Interrupt:
            yield env.timeout(HANDLE_TIME - (env.now - start_time))
        print(f'Agent {ident} finished order at {get_time(env)}')


def agent(env, queue, ident, start_hour, shift_hours):
    # agent starts working
    yield env.timeout(start_hour * 60 * 60)
    print(f'Agent {ident} started shift at {get_time(env)}')
    pick_process = env.process(pick(env, queue, ident))
    yield env.timeout(shift_hours * 60)
    pick_process.interrupt()
    print(f'Agent {ident} ended shift at {get_time(env)}')


def customer_generator(env, queue):
    for n in range(NUM_INTERACTIONS):
        delay = np.random.normal(8 * 60 * 60, 2 * 60)
        yield env.timeout(delay)
        yield queue.put(n)
        print(f'Customer {n} entered queue at {get_time(env)}')


def run_day():
    env = simpy.Environment()
    queue = simpy.Store(env)

    for i in range(1, NUM_AGENTS):
        # first agent always starts at hour 0
        if i == 1:
            env.process(agent(env, queue, ident=i, start_hour=0, shift_hours=SHIFT_LENGTH))

        # last agent always works the end of the day
        elif i == NUM_AGENTS:
            last_shift_hours = SHIFT_LENGTH
            start_hour = 24 - last_shift_hours
            env.process(agent(env, queue, ident=i, start_hour=0, shift_hours=last_shift_hours))

        # otherwise start randomly on a normal dist with most around the mean start time
        else:
            norm_start_hour = int(np.random.normal(
                MEAN_AGENT_START_TIME, AGENT_START_STDEV, 1))
            env.process(agent(
                env, queue, ident=i, start_hour=norm_start_hour, shift_hours=SHIFT_LENGTH))
        
    env.process(customer_generator(env, queue))

    env.run(86400)


def get_time(env):
    hour = int(env.now / 60 / 60)
    mins = 1
    secs = 1

    # return f'hr: {hour}, min: {mins}, sec: {secs}'
    return env.now


def main():

    global CURRENT_DAY
    # Running the sim 5 times, one for each work day
    for i in range(1,2):
        CURRENT_DAY +=1
        print("Running day: ", i)
        run_day()
        print("Day ", i, "complete.")

if __name__ == '__main__':
    main()