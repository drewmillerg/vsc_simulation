""" Simulates the Vehicle Support Center using the Simpy package.

For the simulated process, the agents are considered resources per Simpy documentation
"""

import random
import simpy
import numpy as np
import pandas as pd
import datetime
import csv

""" Global vars
All of the time related variables are in seconds, and outputs converted to 
minutes later when data is recorded/displayed.
"""

# agent starts per day
NUM_EMPLOYEES = 21
# in seconds (480 sec = 8 min) 10.6min = 640 sec, effective handle time, 
#   based on 45 interaction per agent. This was the average as of 2/8/23 with
#   our heaviest volumes
HANDLE_TIME = int(np.random.normal(579, 5, 1)) 
# Customer interaction intervals are on a normal dist based on trailing 30 day data
CUSTOMER_INTERVAL = int(np.random.normal(34, 4, 1))
# CUSTOMER_INTERVAL = 33 # how often customer interactions flow in, cases/ calls come in every 33 seconds in this case, corresponds to about 872 interactions
# in seconds (28800 sec = 480 min = 8 hours) * 7 days
SHIFT_TIME = 27000
# Use the int to change how many days the sim simulates
SIM_TIME = SHIFT_TIME * 5
BREAK_TIME = 1800
WAIT_TIMES = []
CUSTOMERS_HANDLED = 0


class CallCenter:
    """ 
    Represents a call center or customer service center that takes calls or cases 
    """

    def __init__(self, env, num_employees, handle_time):
        self.env = env
        self.staff = simpy.Resource(env, num_employees)
        self.support_time = handle_time

    def support(self, customer):
        # time it takes to handle a call
        random_time = max(1, np.random.normal(self.support_time, 4)) # np.random.normal args (mean, standard dev)
        yield self.env.timeout(random_time)
        print(f"Support finished for {customer} at {self.env.now:.2f}")


def customer(env, name, call_center):
    """ 
    Represents a customer interaction
    """
    global CUSTOMERS_HANDLED

    print(f"Customer {name} enters waiting queue at {env.now:.2f}!")
    # print("Current day: ", get_day(env))
    wait_start = env.now

    with call_center.staff.request() as request:
        yield request

        #dividing the env.now time by 60 so that minutes are shown
        print(f"Customer {name} enterscall at {env.now/60:.2f}")
        yield env.process(call_center.support(name))

        wait_end = env.now
        print(f"Customer {name} left call at {env.now/60:.2f}")

        speed_to_respond = wait_end - wait_start
        WAIT_TIMES.append(speed_to_respond)
        print("Speed to respond: ", speed_to_respond / 60)
        CUSTOMERS_HANDLED +=1


def run_sim(env, num_employees, handle_time, customer_interval, waiting=2):
    """
    Runs the simulation, meant 
    """
    call_center = CallCenter(env, num_employees, handle_time)

    # the range is the number of customers that are already waiting
    # for 5 waiting, you would do range(1,6)
    for i in range (1, waiting + 1):
        env.process(customer(env, num_employees, call_center))

    while True:
        yield env.timeout(random.randint(customer_interval - 1, customer_interval + 1))
        i += 1
        env.process(customer(env, i, call_center))


def max_output_possible():
    """
    Computes the number of interactions that could have been handled during
        the simulation.
    """
    return NUM_EMPLOYEES * SIM_TIME / HANDLE_TIME


def get_day(env):
    """Returns an int that represents the day that the sim env is currently in."""
    return int(env.now // SHIFT_TIME) + 1


def get_time_of_day(env):
    """Returns the time of the current day of the env"""
    return int(env.now / get_day(env))


def get_utilization():
    """
    Computes the actual utilization
    """
    # full capacity is the amount of customers that entered, minus the ones that entered during
    #   one unit of handle time.

    return CUSTOMERS_HANDLED / max_output_possible()

def get_asr():
    """
    Computes Average Speed to Respond
    Must be called after the sim has completed.
    Return: float
    """
    return sum(WAIT_TIMES) / len(WAIT_TIMES) / 60


def vars_to_df():
    """
    Creates dataframe with the inputs and outputs of each sim run
        Pass in the number of customers (interactions) handled
    """
    columns = [
        "Timestamp", "Sim Days", "Number of Employees", "Avg Handle Time",
        "ASR", "Avg Customer Interval", "Interactions Handled", 
        "Utilization"
    ]

    df = pd.DataFrame(columns=columns, index=[0])

    df["Timestamp"] = datetime.datetime.now().strftime(
        'X%m/X%d/%Y X%H:X%M:X%S').replace('X0','X').replace('X','')
    df["Sim Days"] = round(SIM_TIME / 60 / 60 / 7.5, 2)
    df["Number of Employees"] = NUM_EMPLOYEES
    df["Avg Handle Time"] = round(HANDLE_TIME / 60, 2)
    df["ASR"] = round(get_asr(), 2)
    df["Interactions Handled"] = CUSTOMERS_HANDLED
    df["Avg Customer Interval"] = round(CUSTOMER_INTERVAL / 60, 2)
    df["Utilization"] = round(get_utilization(), 2)

    return df


def log_data(df):
    """
    logs the inputs and outputs from the simulation in the "log.csv" file, for later analysis
    """
    df.to_csv('log.csv', mode='a', index=False, header=False)

def main():
    # running the sim
    print("Starting Call Center Simulation")
    my_env = simpy.Environment()
    my_env.process(run_sim(my_env, NUM_EMPLOYEES, HANDLE_TIME, CUSTOMER_INTERVAL))
    my_env.run(until=SIM_TIME)

    # logging and displaying data
    print("Customers handled: " + str(CUSTOMERS_HANDLED))

    my_df = vars_to_df()
    asr = get_asr()
    print(my_df.head())

    log_data(my_df)

if __name__ == "__main__":
    main()