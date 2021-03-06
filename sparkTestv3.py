#Goal: given the time and location
#you must predict the category of the crime
#Start using python3: PYSPARK_PYTHON=python3 /usr/bin/pyspark

#make sure hadoop is started: hdfs dfs -l
#Take a sample of the training csv, and name it train2.csv - otherwise its too big
#put the train2.csv into the HDFS main directory
import pyspark.mllib.regression as mllib_reg
import pyspark.mllib.linalg as mllib_lalg
import pyspark.mllib.classification as mllib_class
import pyspark.mllib.tree as mllib_tree
from pyspark.ml.feature import StringIndexer
import numpy as np
from pyspark.sql import SQLContext
import pandas as pd
import csv
import io
from pyspark.ml.feature import VectorAssembler
from pyspark.mllib.regression import LabeledPoint
from pyspark.sql.functions import col
sqlContext = SQLContext(sc)

#create the framework for the training set dataframe
def loadRecord(line):
    input = io.StringIO(line)
    reader = csv.DictReader(input, fieldnames=['date', 'category_predict', 'description_ignore', ' day_of_week', 'pd_district', 'resolution', 'address', 'x', 'y'])
    return next(reader)

#load the training set
input_file = sc.textFile('train2.csv').map(loadRecord)

#remove the 1st row b/c it has a duplicate data header
header = input_file.first()
rows = input_file.filter(lambda line: line != header)
rows.take(5) #test to see if the data is in


#create dataframe
from pyspark.sql import SQLContext
sqlContext=SQLContext(sc)
data_df = rows.toDF()

#create pandas dataframe
pandas_df = data_df.toPandas()

#clean up the data
#make a new column to track hour

pandas_df['date'] = pd.to_datetime(pandas_df['date'])
pandas_df['day'] = pandas_df['date'].dt.day
pandas_df['month'] = pandas_df['date'].dt.month
pandas_df['year'] = pandas_df['date'].dt.year
pandas_df['hour'] = pandas_df['date'].dt.hour
pandas_df['dayofweek'] = pandas_df['date'].dt.dayofweek
pandas_df['week'] = pandas_df['date'].dt.weekofyear

#truncate the X and Y for similiar locations
#1st decimal is an area of 11.1km
#2nd decimal is an area of 1.1km
#3rd decimal is 110 meters - USING three decimal places
#4th is 11 meters
pandas_df['x_sim'] = pandas_df['x'].str[0:8] #non-negative data
pandas_df['x'] = pandas_df['x'].str[0:8] #non-negative
pandas_df['y_sim'] = pandas_df['y'].str[0:6]

#encode the police dept as a feature
from pyspark.ml.feature import OneHotEncoder, StringIndexer
stringIndexer = StringIndexer(inputCol="pd_district", outputCol="pd_district_Index")
model = stringIndexer.fit(data_df)
indexed = model.transform(data_df)
encoder = OneHotEncoder(dropLast=False, inputCol="pd_district_Index", outputCol="pd")
encoded = encoder.transform(indexed)


#encode the dependent variable - category_predict
classifyIndexer = StringIndexer(inputCol="category_predict", outputCol="category")
classifymodel = classifyIndexer.fit(encoded)
encoded2 = classifymodel.transform(encoded)

#keep the following columns: x, y, hour, day, month, year, dayofweek, week, x_sim, y_sim
#drop the following
cleaned = encoded2.select([c for c in encoded2.columns if c not in{' day_of_week','category_predict','address','date','description_ignore','pd_district','resolution','pd_district_Index'}])

ignore = ['category']
assembler = VectorAssembler(
    inputCols=[x for x in cleaned.columns if x not in ignore],
    outputCol='features')

transformed = assembler.transform(cleaned)


data_transformed = transformed.select(col("category").alias("label"), col("features")).map(lambda row: LabeledPoint(row.label, row.features))

#**************************
# split the training set
train, test = data_transformed.randomSplit([0.7, 0.3], seed = 2)

#naivebayes classifier
#lambda = 1.0
# initialize classifier:
model = mllib_class.NaiveBayes.train(train, 1.0)

# Make prediction and test accuracy.
# Evaluating the model on training data
labelsAndPreds = test.map(lambda p: (p.label, model.predict(p.features)))
trainErr = labelsAndPreds.filter(lambda vp: vp[0] != vp[1]).count() / float(train.count())
print("Training Error = " + str(trainErr))

# Evaluate model on test instances and compute test error
predictions = model.predict(test.map(lambda x: x.features))
labelsAndPredictions = test.map(lambda lp: lp.label).zip(predictions)
testMSE = labelsAndPredictions.map(lambda vp: (vp[0] - vp[1]) * (vp[0] - vp[1])).sum() / float(test.count())
print('Test Mean Squared Error = ' + str(testMSE))


