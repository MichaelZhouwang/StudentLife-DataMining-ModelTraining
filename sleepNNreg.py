import json,csv,sys,os,psycopg2
import numpy as np
from collections import Counter 
from processingFunctions import *
import matplotlib.pyplot as plt
import time
from sklearn.linear_model import LogisticRegression as mlpr
import theano
import theano.tensor as T
from nolearn.lasagne import NeuralNet
import lasagne
# -----------------------------------------------------------------------------------
# This script is intended to train a non-linear estimator for sleep time during nights
# Multi-Layer Perceptron will be used for the estimation (sklearn)
# -----------------------------------------------------------------------------------


def loadSleepLabels(cur,uid):
	uid = uid+'sleep'

	cur.execute('SELECT hour,time_stamp FROM {0}'.format(uid))
	records = cur.fetchall()
	records = sorted(records,key=lambda x:x[1])
	return(np.array(records)) 


# returns duration (seconds) screen remained locked during previous evening and night
# used for Sleep Estimator as feature
def screenLockDur(cur,uid,timestamp):
	totalDur = 0
	uidL = uid + 'lock'
	cur.execute('SELECT * FROM {0} WHERE timeStart>={1} AND timeStop <= {2}'.format(uidL, timestamp-86400, timestamp) )
	records = cur.fetchall()
	
	#keeping only records during night epoch ( 21:00 < t < 10:00)
	tStart = [item[0] for item in records]
	timeEpochs = epochCalc(tStart)

	
	for i in range(0,len(tStart)):
		if timeEpochs[i][0] =='night':
			totalDur += records[i][1] -records[i][0]

	return(totalDur)


# computes duration (seconds) user was stationary during night epoch ( 21:00 < t < 10:00)
# Feature for Sleep Estimator NN
def stationaryDur(cur,uid,timestamp):
	totalDur = 0
	uidS = uid +'act'
	cur.execute('SELECT * FROM {0} WHERE time_stamp>={1} AND time_stamp<={2}'.format(uidS, timestamp-86400, timestamp) )
	records = cur.fetchall()
	
	tStart = [item[0] for item in records]
	timeEpochs = epochCalc(tStart)

	for i in range(1,len(records)):
		# if two consecutive samples are the same and equal to zero (stationary) then calculate duration
		if records[i-1][1] == records[i][1] and records[i][1]==0 and timeEpochs[i][0]=='night':
		
			totalDur += records[i][0] - records[i-1][0] 

	return totalDur


# computes duration (seconds) user's phone was in a silent environment during night epoch ( 21:00 < t < 10:00)
# Feature for Sleep Estimator NN
def silenceDur(cur,uid,timestamp):
	totalDur = 0
	uidSil = uid+'audio'
	cur.execute('SELECT * FROM {0} WHERE time_stamp>={1} AND time_stamp<={2}'.format(uidSil, timestamp-86400, timestamp) )
	records = cur.fetchall()

	tStart = [item[0] for item in records]
	timeEpochs = epochCalc(tStart)

	for i in range(1,len(records)):
		#if two consecutive samples are the same and equal to zero, also in night then their duration
		# is added to the total silence duration
		if records[i-1][1] == records[i][1] and records[i][1]==0 and timeEpochs[i][0]=='night':
			totalDur += records[i][0] - records[i-1][0] 

	return totalDur

#calculates total time phone stayed in dark during night epoch (db is (tstart,tstop))
# Feature for Sleep Estimator NN
def darknessDur(cur,uid,timestamp):
	totalDur = 0
	uidS = uid+'dark'
	#Getting data from database within day period
	cur.execute('SELECT * FROM {0} WHERE timeStart>={1} AND timeStop<={2}'.format(uidS, timestamp-86400, timestamp) )
	records = cur.fetchall()

	#timeEpochs holds tuples of timestamps and their according epochs
	tStart = [item[0] for item in records]
	timeEpochs = epochCalc(tStart)

	for i in range(0,len(records)):

		if timeEpochs[i][0]=='night':
			totalDur += records[i][1] - records[i][0] 

	return totalDur


# returns total charge time during nigth epoch
# Feature for Sleep Estimator NN
def chargeDur(cur,uid,timestamp):
	totalDur = 0
	uidC = uid+'charge'
	#Getting data from database within day period
	cur.execute('SELECT * FROM {0} WHERE start_timestamp>={1} AND end_timestamp<={2}'.format(uidC, timestamp-86400, timestamp) )
	records = cur.fetchall()

	#timeEpochs holds tuples of timestamps and their according epochs
	tStart = [item[0] for item in records]
	timeEpochs = epochCalc(tStart)

	for i in range(0,len(records)):
		if timeEpochs[i][0]=='night':
			totalDur += records[i][1] - records[i][0]

	return totalDur


#Function to fit regression NN with one hidden layer
def regression(X,y):
	print(X.shape,y.shape)
	layers_all = [('input',lasagne.layers.InputLayer),
				   ('dense0', lasagne.layers.DenseLayer),
				   	('output',lasagne.layers.DenseLayer)]

	net = NeuralNet(layers = layers_all,
					 input_shape = (None,X.shape[1]),
					 dense0_num_units = 15,
					 regression=True,
					 output_nonlinearity=None,
					 output_num_units=1,
					 update_learning_rate=0.01,
					 max_epochs=150
					 )
	net.fit(X,y)
	for i in range(5,20):
		a= np.transpose(X[i,:].reshape(X[i,:].shape[0],1))
		
		pr = net.predict(a)
		print(pr,y[i])





def main(argv):
	#connecting to database with error handling
	try:
		con = psycopg2.connect(database='dataset', user='tabrianos')
		cur = con.cursor()

	except psycopg2.DatabaseError as err:
		print('Error %s' % err)
		exit()



	if sys.argv[1]=='-train':
		

		#X = np.empty((len(uids1),4),dtype='float32')
		X =[]
		y= []
		for trainUser in uids1:
			print(trainUser)
			sleepL = loadSleepLabels(cur,trainUser)
			y += [item[0] for item in sleepL]

			# Computing five features to be used for regression of Sleep time, during night epoch:
			# 1) Total time phone stayed in dark environment (darkDur)
			# 2) Total time phone remained locked (sld)
			# 3) Total time audio classifier outputed silence (silDur)
			# 4) Total time activity classifier outputed stationary (statDur)
			# 5) Total charge time

			for i in range(0,len(sleepL)):

				sld = screenLockDur(cur,trainUser,sleepL[i][1])
				
				statDur = stationaryDur(cur,trainUser,sleepL[i][1])
				
			#	silDur = silenceDur(cur,trainUser,sleepL[i][1])
				darkDur = darknessDur(cur,trainUser,sleepL[i][1])
				chDur = chargeDur(cur,trainUser,sleepL[i][1])
				print([sld,statDur,darkDur,chDur])
				X.append( [sld,statDur,darkDur,chDur])
				#convS = conversationStats( cur, trainUser, sleepL[i][1])
				#colS = colocationStats(cur,trainUser,sleepL[i][1])

				#FV = np.concatenate((convS,colS),axis=0)
				#np.append(FV,(sld,statD))
			#print(X)
			#print('----------')
			#print(y)
		
		Xtrain = np.nan_to_num(X)
		Xtrain1 = np.empty((Xtrain.shape[0],Xtrain.shape[1]),dtype='float32')
		print(Xtrain[1,:])
		for i in range(0,Xtrain.shape[0]):

			if np.std(Xtrain[i,:])>0:
				Xtrain1[i,:] = (Xtrain[i,:]-np.mean(Xtrain[i,:]))/np.std(Xtrain[i,:])
		print(Xtrain1[1,:])

		regression(Xtrain1,np.array(y))



		#do stuff
		


















if __name__ == '__main__':
	main(sys.argv[1:])