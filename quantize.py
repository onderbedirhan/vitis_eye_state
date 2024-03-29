import warnings
warnings.filterwarnings('ignore')
import tensorflow as tf
#tf.compat.v1.enable_eager_execution() #enable only for freeze_graph function
import numpy as np
from tensorflow import keras
import os, random
import argparse
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras.preprocessing import image
from tensorflow.python.tools import freeze_graph
from tensorflow.python.framework.convert_to_constants import convert_variables_to_constants_v2
from tensorflow.python.tools import optimize_for_inference_lib
from progressbar import ProgressBar
from tensorflow.python.platform import gfile
#import tensorflow.contrib.decent_q
#from tensorflow_model_optimization.quantization.keras import vitis_quantize
import matplotlib.pyplot as plt
import shutil
from tensorflow_model_optimization.quantization.keras import vitis_quantize


import os
import shutil
from tensorflow.keras.preprocessing.image import ImageDataGenerator

def preprocess(directory_path='data/mrlEyes_2018_01'):
    '''
    if not os.path.exists('data/Train'):
        os.makedirs('data/Train/Open')
        os.makedirs('data/Train/Close')
    
    if not os.path.exists('data/Test'):
        os.makedirs('data/Test/Open')
        os.makedirs('data/Test/Close')

    sessions = [d for d in os.listdir(directory_path) if os.path.isdir(os.path.join(directory_path, d))]
    total = len(sessions)
    count = 0
    
    for session in sessions:
        session_path = os.path.join(directory_path, session)
        participants = [p for p in os.listdir(session_path) if os.path.isdir(os.path.join(session_path, p))]
        
        for participant in participants:
            participant_path = os.path.join(session_path, participant)
            images = os.listdir(participant_path)
            
            if count <= int(total / 2) + 1:
                destination = 'data/Train'
            else:
                destination = 'data/Test'
            
            for img in images:
                src_path = os.path.join(participant_path, img)
                if(int(img.split('_')[4]) == 0):
                    dst_path = os.path.join(destination, 'Close', img)
                else:
                    dst_path = os.path.join(destination, 'Open', img)

                if not os.path.exists(dst_path):  # Check if the destination file already exists
                    shutil.copy(src_path, dst_path)
        
        count += 1
    '''

    # Creating ImageDataGenerator objects for train and test sets
    train = ImageDataGenerator(rescale=1/255, fill_mode='reflect', shear_range=0.2, width_shift_range=0.2, height_shift_range=0.2)        
    test = ImageDataGenerator(rescale=1/255)
    
    # Generating train and test datasets
    train_dataset = train.flow_from_directory("data/Train/", target_size=(150,150), batch_size=32, class_mode='binary', color_mode='grayscale')
    test_dataset = test.flow_from_directory("data/Test/", target_size=(150,150), batch_size=32, class_mode='binary', color_mode='grayscale')
    
    print(test_dataset.class_indices)
    
    return train_dataset, test_dataset

    
      
def classifier_model(train_dataset, test_dataset):
    model = keras.Sequential()

    # Convolutional layer and maxpool layer 1
    model.add(keras.layers.Conv2D(32,(3,3),activation='relu',input_shape=(150,150,1)))
    model.add(keras.layers.MaxPool2D(2,2))

    # Convolutional layer and maxpool layer 2
    model.add(keras.layers.Conv2D(64,(3,3),activation='relu'))
    model.add(keras.layers.MaxPool2D(2,2))

    # Convolutional layer and maxpool layer 3
    model.add(keras.layers.Conv2D(128,(3,3),activation='relu'))
    model.add(keras.layers.MaxPool2D(2,2))

    # Convolutional layer and maxpool layer 4
    model.add(keras.layers.Conv2D(128,(3,3),activation='relu'))
    model.add(keras.layers.MaxPool2D(2,2))
    #model.add(keras.layers.Dropout(0.4))

    # This layer flattens the resulting image array to 1D array
    model.add(keras.layers.Flatten())

    # Hidden layer with 1024 neurons and Rectified Linear Unit activation function 
    model.add(keras.layers.Dense(1024,activation='relu'))
    
    # Hidden layer with 512 neurons and Rectified Linear Unit activation function 
    model.add(keras.layers.Dense(512,activation='relu'))
    #model.add(keras.layers.Dropout(0.4))

    # Output layer with single neuron which gives 0 for Close or 1 for Open 
    #Here we use sigmoid activation function which makes our model output to lie between 0 and 1
    model.add(keras.layers.Dense(1,activation='sigmoid'))

    return model
 
 
def train(train_dataset, test_dataset):
    print("Hello world")
    model = classifier_model(train_dataset, test_dataset)
    
    model.compile(optimizer='adam',loss='binary_crossentropy',metrics=['accuracy'])
    model.fit_generator(train_dataset, 
                        steps_per_epoch = train_dataset.samples//train_dataset.batch_size, 
                        epochs = 1, 
                        validation_data = test_dataset, 
                        validation_steps=test_dataset.samples//test_dataset.batch_size)    
    print(model.summary()) 
    
    scores = model.evaluate(test_dataset, batch_size=32)
    print('Loss: %.3f' % scores[0])
    print('Accuracy: %.3f' % scores[1]) 
    
    # save weights, model architecture & optimizer to an HDF5 format file
    os.system('rm -rf saved_model')
    os.mkdir('saved_model')
    model.save('saved_model/classification_model.h5')


def freeze_graph(model, input_node):
    print("Freeze graph working")
    model  = keras.models.load_model(model)

    # Convert Keras model to ConcreteFunction
    full_model = tf.function(lambda x: model(x))
    full_model = full_model.get_concrete_function(
    tf.TensorSpec(model.inputs[0].shape, model.inputs[0].dtype, name=input_node))
    
    # Get frozen ConcreteFunction
    frozen_func = convert_variables_to_constants_v2(full_model)
    frozen_func.graph.as_graph_def()
    layers = [op.name for op in frozen_func.graph.get_operations()]

    print("Frozen model layers: ")
    for layer in layers:
        print(layer)

    print("Frozen model inputs: ")
    print(frozen_func.inputs)
    print("Frozen model outputs: ")
    print(frozen_func.outputs)
    
    # Save frozen graph from frozen ConcreteFunction to hard drive
    tf.io.write_graph(graph_or_graph_def=frozen_func.graph,
                  logdir="./saved_model",
                  name="frozen_graph.pb",
                  as_text=False)
    return
    

def optimize_graph(input_nodes, output_nodes):
    inputGraph = tf.GraphDef()
    with tf.gfile.Open('frozen_models/frozen_graph.pb', "rb") as f:
        data2read = f.read()
        inputGraph.ParseFromString(data2read)
  
    outputGraph = optimize_for_inference_lib.optimize_for_inference(
              inputGraph,
              input_nodes, # an array of the input node(s)
              output_nodes, # an array of output nodes
              tf.int32.as_datatype_enum)

    # Save the optimized graph'test.pb'
    f = tf.gfile.FastGFile('frozen_models/OptimizedGraph.pb', "w")
    f.write(outputGraph.SerializeToString()) 


def evaluate_graph(graph, batch_size, test_dataset, input_node, output_node):
    input_graph_def = tf.Graph().as_graph_def()
    input_graph_def.ParseFromString(tf.io.gfile.GFile(graph, "rb").read())

    tf.import_graph_def(input_graph_def,name = '')

    # Get input placeholders & tensors
    images_in = tf.compat.v1.get_default_graph().get_tensor_by_name(input_node)
    labels = tf.compat.v1.placeholder(tf.int32,shape = [None,2])

    # get output tensors
    logits = tf.compat.v1.get_default_graph().get_tensor_by_name(output_node)
    predicted_logit = tf.argmax(input=logits, axis=1, output_type=tf.int32)
    ground_truth_label = tf.argmax(labels, 1, output_type=tf.int32)

    # Define the metric and update operations
    tf_metric, tf_metric_update = tf.compat.v1.metrics.accuracy(labels=ground_truth_label,
                                                                predictions=predicted_logit,
                                                                name='acc')

    with tf.compat.v1.Session() as sess:
        progress = ProgressBar()        
        sess.run(tf.compat.v1.initializers.global_variables())
        sess.run(tf.compat.v1.initializers.local_variables())

        feed_dict={images_in: test_dataset} #, labels: y_batch}
        acc = sess.run(tf_metric_update, feed_dict)
        print ('Graph accuracy with validation dataset: {:1.4f}'.format(acc))

    
def test(model, test_path):   
    model  = keras.models.load_model(model)
    #inp = model.input
    #output = model.output
    #print(inp, output)
    
    filename = random.choice(os.listdir(test_path))
    path = test_path + filename
    
    img = image.load_img(path,target_size=(150,150))    
    plt.imshow(img)
 
    Y = image.img_to_array(img)    
    X = np.expand_dims(Y,axis=0)
    val = model.predict(X)
    val = int(val[0][0])
    print('value = ', val)
    if val == 1:        
        plt.xlabel("Open",fontsize=30)        
    
    elif val == 0:        
        plt.xlabel("Close",fontsize=30)
    plt.show()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--graph', type=str, default='./quantize_results/quantize_eval_model.pb', help='graph file (.pb) to be evaluated')
    parser.add_argument('--batch_size', type=int, default=32, help='Evaluation batchsize, must be integer value') 
    parser.add_argument('-d', '--image_dir', type=str, default='data', help='Path to folder of images.')  
    parser.add_argument('-m', '--model',     type=str, default='saved_model/classification_model.h5', help='Path of the float model.')
    parser.add_argument('--input_nodes', type=str, default='', help='List of input nodes of the graph.')
    parser.add_argument('--output_nodes', type=str, default='', help='List of output nodes of the graph.')   
    args = parser.parse_args()

    train_dataset, test_dataset = preprocess(args.image_dir)
    #train(train_dataset, test_dataset)   
    #freeze_graph(args.model, args.input_nodes)
    #optimize_graph(args.input_nodes, args.output_nodes)
    #evaluate_graph(args.graph, args.batch_size, test_dataset, args.input_node, args.output_node)
    #test(args.model, args.imagfe_dir)
    model  = keras.models.load_model('saved_model/classification_model.h5')

    quantizer = vitis_quantize.VitisQuantizer(model)
    quantized_model = quantizer.quantize_model(calib_dataset=train_dataset[0:500])
    quantized_model.save("quantized_model.h5")    
    
        
if __name__ == '__main__':
    main()                              