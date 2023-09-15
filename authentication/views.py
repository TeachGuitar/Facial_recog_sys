import datetime
import tempfile
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from .tokens import generate_token
from django.core.mail import EmailMessage
from fac_rec_sys import settings
from django.contrib import messages
import cv2
import numpy as np
import mediapipe as mp
from PIL import Image
import os
from .Google.Google import Create_Service
from googleapiclient.http import MediaFileUpload

from django.contrib.auth.hashers import check_password

# Create your views here
#@csrf_exempt
def signin(request):
    if request.user.is_authenticated:
        return redirect('index')  # Redirect to the index view if user is already authenticated
    
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('index')
        else:
            messages.error(request, 'Wrong username or password')
            return redirect('signin')

    return render(request, "authentication/login.html")

@csrf_exempt
def signup(request):

    if request.method == "POST":
        username = request.POST['username']
        fname = request.POST['fname']
        lname = request.POST['lname']
        email = request.POST['email']
        pass1 = request.POST['pass1']

        try:
            myuser = User.objects.create_user(username, email, pass1)
            myuser.first_name = fname
            myuser.last_name = lname
            myuser.is_active = False
            myuser.save()

            #Email Address Confirmation Email
            current_site = get_current_site(request)
            email_subject = "Confirm your email @scanVerifyHub Login!!"
            message = render_to_string('email_confirmation.html',{
                'name' : myuser.first_name,
                'domain' : current_site.domain,
                'uid' : urlsafe_base64_encode(force_bytes(myuser.pk)),
                'token' : generate_token.make_token(myuser)
            })
            email = EmailMessage(
                email_subject,
                message,
                settings.EMAIL_HOST_USER,
                [myuser.email]
            )
            email.fail_silently = True
            email.send()
            messages.success(request, 'We send you the verification email already. please click on the link to complete you set up account')
            # Redirect to a success page or return a success message
            return redirect('signin')
        except Exception as e:
            return JsonResponse({'error': str(e)})

    return render(request, "authentication/signup.html")

def check_username_availability(request):
    if request.method == "GET":
        username = request.GET.get('username', None)
        if username is not None:
            user_exists = User.objects.filter(username=username).exists()
            return JsonResponse({'available': not user_exists})
        else:
            return JsonResponse({'error': 'Invalid request'}, status=400)
    else:
        return JsonResponse({'error': 'Invalid request'}, status=400)
    
def check_email_availability(request):
    if request.method == "GET":
        email = request.GET.get('email', None)
        if email is not None:
            email_exists = User.objects.filter(email=email).exists()
            return JsonResponse({'available': not email_exists})
        else:
            return JsonResponse({'error': 'Invalid request'}, status=400)
    else:
        return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
def index(request):
    user = request.user
    user_info = {
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        # Add more user-specific attributes as needed
    }

    return render(request, 'index.html', {'user_info': user_info})
    #return render(request, 'index.html')
    

def signout(request):
    logout(request)
    messages.success(request,"Logout successfully")
    return redirect('signin')

def activate(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        myuser = User.objects.get(pk=uid)
    except(TypeError, ValueError, OverflowError, User.DoesNotExist):
        myuser = None

    if myuser is not None and generate_token.check_token(myuser, token):
        myuser.is_active = True
        myuser.save()
        login(request, myuser)
        return redirect('index')
    else:
        messages.error(request, 'Failed verification')
        return redirect('signin')

def feed_back(image):
    # Read the uploaded image as a NumPy array using OpenCV
    nparr = np.frombuffer(image, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    # Initialize the MediaPipe Face Detection and Face Mesh modules
    mp_face_mesh = mp.solutions.face_mesh
    mp_drawing = mp.solutions.drawing_utils
    gray_frame = cv2.cvtColor( image, cv2.COLOR_BGR2GRAY)
    brightness = np.mean(gray_frame)
    # Convert the image to RGB format (required by MediaPipe)
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    # Initialize the MediaPipe Face Mesh model
    with mp_face_mesh.FaceMesh(min_detection_confidence=0.5, min_tracking_confidence=0.5) as face_mesh:

        # Perform face mesh detection on the image
        results_mesh = face_mesh.process(image_rgb)

        # Initialize variables to track landmarks
        left_eye_center = None
        right_eye_center = None
        nose_landmark = None

        pitch = 0
        yaw = 0
        cv2.putText(image, f'Brightness: {brightness:.2f}', (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

        # Draw face landmarks on the image
        if results_mesh.multi_face_landmarks:
            for landmarks in results_mesh.multi_face_landmarks:
                mp_drawing.draw_landmarks(image, landmarks, mp_face_mesh.FACEMESH_CONTOURS, mp_drawing.DrawingSpec(color=(0, 0, 255), thickness=1, circle_radius=1))

                # Extract specific landmarks for orientation estimation (e.g., left eye, right eye, nose, etc.)
                left_eye_landmark = landmarks.landmark[159]  # Left eye inner corner
                right_eye_landmark = landmarks.landmark[386]  # Right eye inner corner
                nose_landmark = landmarks.landmark[6]  # Nose tip

                # Calculate head orientation angles (pitch and yaw)
                left_eye_x = left_eye_landmark.x * image.shape[1]
                right_eye_x = right_eye_landmark.x * image.shape[1]
                nose_x = nose_landmark.x * image.shape[1]

                # Calculate pitch (up-down) angle
                pitch = np.degrees(np.arcsin(nose_landmark.y - ((left_eye_landmark.y + right_eye_landmark.y) / 2)))

                # Calculate yaw (left-right) angle
                yaw = np.degrees(np.arctan2(nose_x - ((left_eye_x + right_eye_x) / 2), image.shape[1]))

                # Display the angles on the image
                cv2.putText(image, f'Pitch: {pitch:.2f} deg', (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
                cv2.putText(image, f'Yaw: {yaw:.2f} deg', (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

    #cv2.imwrite('output_image.png', image)
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    image = Image.fromarray(image)
    # Create a response with the modified image
    return image, pitch, yaw, brightness

@csrf_exempt
def capture_frame(request):
    if request.method == 'POST':
        image_file = request.FILES.get('image')

        if image_file:
            image_data = image_file.read()

            # Call the feed_back function to get the dictionary
            processed_image = feed_back(image_data)[0]

            pitch = feed_back(image_data)[1]
            yaw = feed_back(image_data)[2]
            brightness = feed_back(image_data)[3]

            detect_data = detect_headangle(pitch,yaw,brightness)

            # Create a response with the processed image and additional data
            response = HttpResponse(content_type='image/jpeg')
            processed_image.save(response, 'JPEG')

            response_data = {
                'pitch': str(round(pitch, 2)),
                'yaw': str(round(yaw, 2)),
                'brightness': str(round(brightness, 2)),
            }

            responsedetect_data = {
                'angle':  detect_data[0],
                'brigthness': detect_data[1],
            }

            # Send the response data as JSON to the frontend
            return JsonResponse(responsedetect_data)
        else:
            return JsonResponse({'error': 'No image file received'}, status=400)

    return JsonResponse({'error': 'Invalid request method'}, status=400)

def detect_headangle(pitch, yaw, brigthness):
    if 2 >= pitch >= 0.5 and -1 <= yaw <= 1:
        angle_value = "look forward"

    # Check if it's a left turn
    elif 2 >= pitch >= 0.5 and yaw >= 1:
        angle_value = "Turn Left"
    
    # Check if it's a right turn
    elif 2 >= pitch >= 0.5 and yaw <= -1:
        angle_value = "Turn Right"

    # Check if it's a look forward
    elif 2 <= pitch and -1 <= yaw <= 1:
        angle_value = "look forward down"

    elif pitch <= 0.5 and -1 <= yaw <= 1:
        angle_value = "look forward up"

    # Check if it's a left turn
    elif 2 <= pitch and yaw >= 1:
        angle_value = "Turn Left down"
    
    # Check if it's a right turn
    elif 2 <= pitch and yaw <= -1:
        angle_value = "Turn Right down"
    
    # Check if it's a left turn
    elif pitch <= 0.5 and yaw >= 1:
        angle_value = "Turn Left up"
    
    # Check if it's a right turn
    elif pitch <= 0.5 and yaw <= -1:
        angle_value = "Turn Right up"
    else:
        angle_value = "Face doesn't detect"
    
    if brigthness < 100:
        brigthbess_value = "too dark"
    elif brigthness > 200:
        brigthbess_value = "too bright"
    else:
        brigthbess_value = "good brightness"

    return angle_value, brigthbess_value

@csrf_exempt
def video_receive(request):
    if request.method == 'POST':
        video_file = request.FILES.get('video')
        user = request.user

        if video_file:

            # Save the uploaded video file to a temporary location on disk
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                for chunk in video_file.chunks():
                    temp_file.write(chunk)
                temp_file_path = temp_file.name
            
            # Define the base directory where you want to save the videos
            current_time = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            upload_video_to_google_drive(temp_file_path, f'{user.first_name}_{current_time}.webm', f'{user.first_name}')

            # Remove the temporary file
            os.remove(temp_file_path)

            return JsonResponse({'message': 'Video received and saved successfully'})
        else:
            return JsonResponse({'error': 'No video file received'}, status=400)

    return JsonResponse({'error': 'Invalid request method'}, status=400)

from googleapiclient.http import MediaFileUpload
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

def get_or_create_folder(service, parent_folder_id, folder_name):
    # Search for the folder by name within the parent folder
    query = f"'{parent_folder_id}' in parents and name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder'"
    results = service.files().list(q=query, fields='files(id)').execute()
    folders = results.get('files', [])

    if folders:
        # Folder with the given name exists, return its ID
        return folders[0]['id']
    else:
        # Folder doesn't exist, create it within the parent folder
        folder_metadata = {
            'name': folder_name,
            'parents': [parent_folder_id],
            'mimeType': 'application/vnd.google-apps.folder'
        }
        folder = service.files().create(body=folder_metadata, fields='id').execute()
        return folder.get('id')

def upload_video_to_google_drive(video_file, file_name, parent_folder_name, credentials_file=r"C:\Users\yossakorn\Desktop\Facial_recog_sys\authentication\Google\credentials.json"):
    try:
        # Authenticate and create a Google Drive service
        CLIENT_SECRET_FILE = credentials_file
        API_NAME = 'drive'
        API_VERSION = 'v3'
        SCOPE = ['https://www.googleapis.com/auth/drive']

        service = Create_Service(CLIENT_SECRET_FILE, API_NAME, API_VERSION, SCOPE)

        # Get or create the parent folder by name
        parent_folder_id = get_or_create_folder(service, '14zQ5OnY3GrY2dvcUo1kNUNaUvUxkfHLo', parent_folder_name)

        # Prepare metadata for the video file
        video_metadata = {
            'name': file_name,
            'parents': [parent_folder_id],
        }

        # Create a media object for the video file to be uploaded
        media = MediaFileUpload(video_file, mimetype='video/webm', resumable=True)

        # Upload the video file to Google Drive
        response = service.files().create(
            body=video_metadata,
            media_body=media,
            fields='id'
        ).execute()

        # Return the file ID of the uploaded video file
        return response.get('id')

    except HttpError as e:
        # Handle HTTP errors
        print(f"HTTP error uploading video to Google Drive: {e}")
        return None
    except Exception as e:
        # Handle other exceptions that may occur during the upload
        print(f"Error uploading video to Google Drive: {e}")
        return None
