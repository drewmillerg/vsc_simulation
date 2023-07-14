"""
Simulation of Vehicle Support Center operations (24hr).

Requirements:
    - Must be able to simulate 24 hours
    - Must be able to simulate the calls coming in on a definable distribution
    - Must be able to simulate the shifts starting at defined times
    - Must be able to simulate the whole week
    - ASR calculation must be an average of each interaction, NOT the average 
        of the day to day ASR

Open issues:
    - wait times from previous hour are not carrying over to next hour
"""

import random
import simpy
import numpy as np
import pandas as pd
import datetime
import csv
import math

""" Global vars
All of the time related variables are in seconds, and outputs converted to 
minutes later when data is recorded/displayed.
"""
# agent starts per day
AGENT_STARTS = 10
# tracks the agents currently working
#   key is int tracking the agent that is starting
AGENT_NO = 0
AGENTS_WORKING = {}
# tracks the number of agents that are available to work the rest of the day
BENCH = -1
# stats about the interactions that VSC handless in a day (calculate based on 
# stat analysis)
INTERACTIONS_MEAN = 872
INTERACTIONS_STDEV = 40
# this is set for the day by the setter function
INTERACTIONS_TODAY = 0
# in seconds (480 sec = 8 min) 10.6min = 640 sec, effective handle time, 
#   based on 45 interaction per agent. This was the average as of 2/8/23 with
#   our heaviest volumes
HANDLE_TIME = int(np.random.normal(579, 5, 1)) 
# Customer interaction intervals are on a normal dist based on trailing 30 day 
#   data
# CUSTOMER_INTERVAL = 33 # how often customer interactions flow in, cases/ 
#   calls come in every 33 seconds in this case, corresponds to about 872 interactions
CUSTOMER_INTERVAL = 0
HOUR_INTERVAL = 0

# 60 seconds * 60 minutes = 1 hour
SIM_TIME = 60 * 60
CURRENT_HOUR = 0
WAIT_TIMES = []
CUSTOMERS_HANDLED = 0
CURRENT_HOUR = 0
# number of customers waiting when a given execution of the sim starts
CUSTOMERS_WAITING = []
# the wait times for the customers that did not get processed last hour
RESIDUAL_WAIT_TIMES = []
# dictionary for setting the proportion of customer interactions that come
#   in for each hour
WORK_PORTIONS = {
    '0': .002, '1': .002, '2': .004, '3': .007, '4': .026, '5': .053,
    '6': .080, '7': .099, '8': .101, '9': .102, '10': .099, '11': .103,
    '12': .099, '13': .073, '14': .046, '15': .033, '16': .024, '17': .015,
    '18': .010, '19': .007, '20': .004, '21': .003, '22': .003, '23': .003
}

AGENT_PORTIONS = {
    '0': .04, '1': .04, '2': .04, '3': .09, '4': .18, '5': .4,
    '6': .57, '7': .62, '8': .74, '9': .79, '10': .84, '11': .88,
    '12': .84, '13': .75, '14': .57, '15': .4, '16': .31, '17': .22,
    '18': .22, '19': .13, '20': .09, '21': .09, '22': .04, '23': .04   
}


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


def set_agents_working(hour=12):
    """
    Setter for AGENTS_WORKING
    This will be used to determine how many agents are working, each time the
        simulation simulates an hour.

    TODO: make the number of employees returned dynamic, based on the number 
            of total agent starts and the time of day.
    """
    global CURRENT_HOUR, AGENT_NO, AGENTS_WORKING, BENCH
    # simplified version
    # AGENTS_WORKING = 18

    # filling the bench
    if BENCH == -1:
        # subtracting 1 to account for the night agent
        BENCH = AGENT_STARTS -1

    # setting up AGENTS_WORKING for off hours
    # if it's earler than 3 am, night agent from previous day will be working
    if CURRENT_HOUR < 3:
        if CURRENT_HOUR == 0:
            add_agent(4, -1)
        else:
            decrement_agent_hours_left()

    # if it's later than 9 pm
    elif CURRENT_HOUR > 21:
        # if it's 10 pm, there is one agent and they have 2 hours left 
        if CURRENT_HOUR == 22:
            AGENTS_WORKING = {-1: 2}
        else:
            decrement_agent_hours_left()

    # hours between 3 am and 9 pm inclusive
    else:
        previous_agent_count = get_agents_working_count()
        decrement_agent_hours_left()
        ideal_agents_working = int(AGENT_STARTS * AGENT_PORTIONS[str(CURRENT_HOUR)])
        print("Ideal number of agents working:", ideal_agents_working)
        ideal_agents_added = ideal_agents_working - previous_agent_count

        # case where staff and caseload are ramping up
        if ideal_agents_working > get_agents_working_count():
            # case where there are enough agents on the bench to fill the needed workcload
            if ideal_agents_added <= BENCH:
                for i in range(ideal_agents_added):
                    add_agent()

            # case where there are not enough on the bench for ideal workload
            elif ideal_agents_added > BENCH:
                for i in range(BENCH):
                    add_agent()
    
    print("On bench:", BENCH)
    # for agent in AGENTS_WORKING:
    #     print("Agent", agent, "has", AGENTS_WORKING[agent], "hours left." )
                

    
def add_agent(hours_left = 8, this_agent = 0):
    """
    Adds one agent to the dict of currently working agents.
        if this_agnet variable is left default it means that this is the first
        agent of the day (technically started yesterday), which is why the 
        AGENT_NO does not get incremented.
    """
    global AGENT_NO
    global AGENTS_WORKING
    global BENCH
    # default adds an agent to AGENTS_WORKING
    if this_agent == 0:
        print("Added agent", AGENT_NO, "to AGENTS_WORKING, with", hours_left, "hours left.")
        AGENT_NO += 1
        AGENTS_WORKING[AGENT_NO] = hours_left
        BENCH -= 1
    # adds specific agent
    else:
        print("Added agent", this_agent, "to AGENTS_WORKING, with", hours_left, "hours left.")
        AGENTS_WORKING[this_agent] = hours_left


def decrement_agent_hours_left():
    """
    Subtracts an hour from the time each agent has left to work
    if the time they have left is 0, it removes them.
    """
    global AGENTS_WORKING 
    
    for i in tuple(AGENTS_WORKING):
        try:
            if AGENTS_WORKING[i] == 0:
                del AGENTS_WORKING[i]
            else:
                AGENTS_WORKING[i] -=1
        except:
            print("Error: Out of bounds", i, "for AGENTS_WORKING dict.")
            continue


def get_agents_working_count():
    """
    Getter for AGENTS WORKING
    """
    return len(AGENTS_WORKING)


def day_customer_interval(hour=12):
    """
    Provides the interval upon which the work comes in for a given sim 
        execution.

    Returns: int representing the number of seconds between customer 
        interactions coming in overall for an entire day.
    """
    global INTERACTIONS_MEAN, INTERACTIONS_STDEV, CUSTOMER_INTERVAL

    interactions = int(
        np.random.normal(INTERACTIONS_MEAN, INTERACTIONS_STDEV, 1))
    day_seconds = 60 * 60 * 12
    CUSTOMER_INTERVAL = int(day_seconds / interactions)

    return CUSTOMER_INTERVAL


def hour_customer_interval(hour=12):
    """
    Provides the interval upon which the work comes in for a given hour.
    Assumes: 
        INTERACTIONS_TODAY has been set.
        CURRENT_HOUR has been set.

    Returns: int representing the number of seconds between customer 
        interactions coming in.
    """
    # global HOUR_INTERVAL
    # # portion of total interactions that are expected to come in this hour
    # portion = WORK_PORTIONS[str(hour)]
    # print("portion of work", portion)
    # day_interactions = int(
    #     np.random.normal(INTERACTIONS_MEAN, INTERACTIONS_STDEV, 1))
    # print("day interactions:", day_interactions)
    # hour_interactions = portion * day_interactions
    # HOUR_INTERVAL = int(60 * 60 * 24 / hour_interactions)

    global HOUR_INTERVAL

    interactions_this_hour = int(INTERACTIONS_TODAY * WORK_PORTIONS[str(CURRENT_HOUR)])
    print("Interactions for hour", CURRENT_HOUR, " are:", interactions_this_hour)
    HOUR_INTERVAL = int(3600 / interactions_this_hour)
    print("Customer interval for this hour is:", HOUR_INTERVAL, "seconds.")
    return HOUR_INTERVAL


def set_interactions_today():
    global INTERACTIONS_TODAY

    INTERACTIONS_TODAY = int(
        np.random.normal(INTERACTIONS_MEAN, INTERACTIONS_STDEV, 1))


def customer(env, name, call_center, wait_time=0):
    """ 
    Represents a customer interaction

    wait_time: int representing the number of seconds the customer has been 
        waiting.
    """
    global CUSTOMERS_HANDLED, CUSTOMERS_WAITING

    
    # print("Current day: ", get_day(env))
    
    wait_start = (env.now - wait_time)
    print(f"Customer {name} enters waiting queue at {wait_start:.2f}!")
    # adding a customer to the list waiting
    # 2d array that holds the cust name, their wait time if they are still in 
    #    the waiting queue

    CUSTOMERS_WAITING.append([name, SIM_TIME - wait_start])

    with call_center.staff.request() as request:
        yield request

        #dividing the env.now time by 60 so that minutes are shown
        print(f"Customer {name} enterscall at {env.now/60:.2f}")
        yield env.process(call_center.support(name))   

        wait_end = env.now
        CUSTOMERS_WAITING.pop(0)
        print(f"Customer {name} left call at {env.now/60:.2f}")

        speed_to_respond = wait_end - wait_start
        WAIT_TIMES.append(speed_to_respond)
        print("Speed to respond: ", speed_to_respond / 60)
        CUSTOMERS_HANDLED +=1



def run_sim(env, num_employees, handle_time, customer_interval, waiting=2):
    """
    Runs the simulation, simulates one hour per execution. 
    """
    global CUSTOMERS_WAITING
    # showing the customers waiting
    print("Customers waiting:", len(CUSTOMERS_WAITING))
    

    call_center = CallCenter(env, num_employees, handle_time)

    # the range is the number of customers that are already waiting
    # for 5 waiting, you would do range(1,6)
    if len(CUSTOMERS_WAITING) == 0:
        for i in range (1, 2):
            env.process(customer(env, num_employees, call_center))
    else:

        for i in range (1, len(CUSTOMERS_WAITING)):
            env.process(customer(env, num_employees, call_center, CUSTOMERS_WAITING[i-1][1]))

    while True:
        yield env.timeout(random.randint(customer_interval - 1, customer_interval + 1))
        try:
            i += 1
        except: i = 1
        this_customer = customer(env, i, call_center)
        env.process(this_customer)
        # if env.now() == SIM_TIME:




def simulate_day():
    """runs the sim for 24 hours, tracking the necessary variables"""
    global CURRENT_HOUR

    for i in range(0, 24):
        CURRENT_HOUR = i
        set_interactions_today()
        set_agents_working()
        my_env = simpy.Environment()
        interval = hour_customer_interval(CURRENT_HOUR)
        agent_count = get_agents_working_count()
        my_env.process(run_sim(my_env, agent_count, HANDLE_TIME, interval))
        my_env.run(until=SIM_TIME)

        # logging and displaying data
        print("Customers handled: " + str(CUSTOMERS_HANDLED))

        my_df = vars_to_df()
        asr = get_asr()
        print(my_df.head())

        log_data(my_df)


def max_output_possible():
    """
    Computes the number of interactions that could have been handled during
        the simulation.
    """
    return AGENT_STARTS * SIM_TIME / HANDLE_TIME


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
        "Timestamp", "Current Hour", "Agents Working", "Avg Handle Time",
        "ASR", "Customer Interval", "Interactions Handled", 
        "Utilization"
    ]

    df = pd.DataFrame(columns=columns, index=[0])

    df["Timestamp"] = datetime.datetime.now().strftime(
        'X%m/X%d/%Y X%H:X%M:X%S').replace('X0','X').replace('X','')
    df["Current Hour"] = round(CURRENT_HOUR)
    df["Agents Working"] = get_agents_working_count()
    df["Avg Handle Time"] = round(HANDLE_TIME / 60, 2)
    df["ASR"] = round(get_asr(), 2)
    df["Interactions Handled"] = CUSTOMERS_HANDLED
    df["Customer Interval"] = round(HOUR_INTERVAL / 60, 2)
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
    simulate_day()


if __name__ == "__main__":
    main()