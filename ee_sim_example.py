#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Nov  5 11:38:41 2024

@author: frank
"""

try:
    from IPython import get_ipython
    get_ipython().magic('clear')
    get_ipython().magic('reset -f')
except:
    pass

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


def get_collisions_random(number_transmissions, sim_end, transmission_duration):
    
    # get transmission start times
    t_start = np.random.uniform(0, sim_end, number_transmissions)
    
    # sort the start times to efficiently check for overlaps
    t_start.sort()
    
    # since all durations are identical, checking adjacent elements is sufficient
    diffs = np.diff(t_start)
    
    # check overlaps with previous and next transmission
    overlap_prev = np.insert(diffs < transmission_duration, 0, False)
    overlap_next = np.append(diffs < transmission_duration, False)
    
    # a collision occurs if it overlaps with either
    collisions = overlap_prev | overlap_next
    
    return collisions.astype(int)

#%%Sim1: 
#how long to simulate?
sim_duration = 3600
sim_duration_shorter = [sim_duration, sim_duration*0.9, sim_duration*0.75, sim_duration*0.5, sim_duration*0.25, sim_duration*0.1]

#number transmission array
number_transmissions = [1000,2000,3000,4000,5000,6000,7000,8000,9000,10000]

#transmission duration, power, energy, payload
transmission_duration = 0.02 #s
power = 0.01 #W (10mW as per slide 50)
energy_demand = transmission_duration*power
idle_power = 0.0001 #W (0.1mW as per slide 50)
payload = 100 #B

#empty arrays to count collisions and assess collision probability
collisions = np.zeros(len(number_transmissions))
collision_probability = np.zeros(len(number_transmissions))
collisions_shorter = np.zeros(len(sim_duration_shorter))
collision_probability_shorter = np.zeros(len(sim_duration_shorter))

#theoretical calculation
probab_per_transmission = 1 - ((transmission_duration*2)/sim_duration)
collision_probab_theoretical = np.zeros((len(number_transmissions)))

#sim 3600s
for i in range(len(number_transmissions)):
    collisions[i] = np.sum(get_collisions_random(number_transmissions[i],sim_duration,transmission_duration))
    collision_probability[i] = collisions[i]/number_transmissions[i]
    collision_probab_theoretical[i] = 1 - probab_per_transmission**(number_transmissions[i] - 1)

#sim shorter
for i in range(len(sim_duration_shorter)):
    collisions_shorter[i] = np.sum(get_collisions_random(number_transmissions[0],sim_duration_shorter[i],transmission_duration))
    collision_probability_shorter[i] = collisions_shorter[i]/number_transmissions[0]



#assumption: 100B transmission, 10mW * 0.02s
e_i_overall = energy_demand/payload #overall EI, independent on collisions
print('general EI ' + str(e_i_overall))
e_i_collision = energy_demand/(payload*(1-collision_probability)) #consider collisions
print('EI with collision: 1000, ..., 10,000 devices ' + str(e_i_collision))
#consider idle and collisions
e_i_collision_idle = (energy_demand + (sim_duration-transmission_duration)*idle_power)/(payload*(1-collision_probability))
print('and with idle ' + str(e_i_collision_idle))

#now consider reduced duration and number messages; shorter duration and less messages in same relation
e_i_shorter = (energy_demand + (np.array(sim_duration_shorter)-transmission_duration)*idle_power)/(payload*(1-collision_probability_shorter))
print('and for shorter inter-transmission times ' + str(e_i_shorter))

n = 3
colors = plt.cm.copper(np.linspace(0.1,0.9,n))
plt.figure(1, figsize=(5, 3))  
plt.plot(number_transmissions, e_i_collision,  color=colors[0], linewidth='2', label='collisions')
plt.plot(number_transmissions, e_i_collision_idle,  color=colors[1], linewidth='2', label='coll. and idle')
plt.plot(3600/np.array(sim_duration_shorter)*1000, e_i_shorter,  color=colors[2], linewidth='2', label='transm. rate')

plt.grid(which='major')
plt.ylabel('energy intensity [J/Byte]')
plt.xlabel('messages per hour')
plt.legend(loc='best', ncol=1, labelspacing = 0.1, borderaxespad = 0.2, columnspacing = 1, fontsize = 12)
plt.show()

