from flask import Flask, send_from_directory, request
import os

app = Flask(__name__)

# Define the directory where your images are stored
IMAGE_FOLDER = 'images'
app.config['UPLOAD_FOLDER'] = IMAGE_FOLDER

if not os.path.exists(IMAGE_FOLDER):
    os.makedirs(IMAGE_FOLDER)

@app.route('/getfile/<filename>')
def send_image(filename):
    if filename:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    else:
        return "Filename not provided", 400
    
@app.route('/helloworld', methods=['GET'])
def hello_world():
    # return web reponse "hello world"
    return 

# Define a route to save a file to the images folder
@app.route('/save_image', methods=['POST'])
def save_image():
    # Get the image file from the request
    image_file = request.files['image']

    # Save the image file to the images folder
    image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_file.filename)
    image_file.save(image_path)

    # Return a success message
    return {'message': f'Image saved to {image_path}'}

if __name__ == '__main__':
    app.run(
        host="172.169.20.2",
        port=6000,
        debug=True,
    )
    
    