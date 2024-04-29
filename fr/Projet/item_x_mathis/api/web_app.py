from flask import Flask, send_from_directory, request, send_file, make_response
import os
import json
from PIL import Image
import urllib.parse

app = Flask(__name__)

# Define the directory where your images are stored
IMAGE_FOLDER = 'data/images'
app.config['UPLOAD_FOLDER'] = IMAGE_FOLDER

if not os.path.exists(IMAGE_FOLDER):
    os.makedirs(IMAGE_FOLDER)

@app.route('/getfile/<filename>')
def send_image(filename):
    if filename:
        decoded_string = urllib.parse.unquote(filename)
        return send_from_directory(app.config['UPLOAD_FOLDER'], decoded_string)
    else:
        return "Filename not provided", 400
    
@app.route('/getfilev2/<filename>')
def send_image_v2(filename):
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(filepath):
        print("File not found")
        return "Image not found", 404
    
    # Create response with image file and EXIF data
    response = make_response(send_file(filepath, as_attachment=True))
    response.headers['Content-Type'] = 'application/octet-stream'

    return response
    
# Define a route to save a file to the images folder
@app.route('/save_image', methods=['POST'])
def save_image():
    # Get the image file from the request
    image_file = request.files['image']

    # Save the image file to the images folder
    image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_file.filename)
    
    # check if image already exists
    if os.path.exists(image_path):
        return {'message': f'Image already exists at {image_path}'}
    else:
        image_file.save(image_path)
        return {'message': f'Image saved to {image_path}'}

if __name__ == '__main__':
    app.run(
        host="172.169.20.2",
        port=5000,
        debug=True,
    )
    
    print(app.url_map)
    
    