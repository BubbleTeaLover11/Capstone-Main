from flask import Flask, request, jsonify
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import os
from dotenv import load_dotenv
from HTTP_funcs import (
    _get, _put, _post, _delete, _set_payload, _search_for_experience
)
from flask_cors import CORS
from google.cloud import storage
from bson.objectid import ObjectId
from openai import OpenAI

load_dotenv()
app = Flask(__name__)
# Initialize CORS (Cross-Origin Resource Sharing) for React frontend
CORS(app)
USER = os.environ.get('MONGO_USER').strip("\"")
PASSWORD = os.environ.get('PASSWORD').strip("\"")
uri = (
    f"mongodb+srv://{USER}:{PASSWORD}@capstone.fw3b6.mongodb.net/?"
    "retryWrites=true&w=majority&appName=Capstone"
)
client = MongoClient(uri, server_api=ServerApi('1'))
openaiclient = OpenAI(
    api_key=os.environ.get('OPENAI_API_KEY')
)


@app.route("/debug-env")
def debug_env():
    return {
        "MONGO_USER": os.getenv("MONGO_USER"),
        "PASSWORD": os.getenv("PASSWORD")
    }


def general_request(request: object, collection: object) -> None:

    if request.method == 'POST':
        # Add Data
        try:
            response = {
                "Message": "Success",
                "ID": _post(collection, request.get_json())
            }
        except Exception as exception:
            response = {
                'Message': f"Failed: {exception} raised"
            }
        return jsonify(response)

    if request.method == 'GET':
        # Get Data
        try:
            # filters = request.json
            filters = request.args.to_dict()
            response_data = _get(filters, collection)
            response = {
                "Message": "Success",
                "data": response_data
            }
        except Exception as exception:
            response = {
                'Message': f"Failed: {exception} raised"
            }
        return jsonify(response)

    if request.method == 'DELETE':
        # Delete Data
        try:
            # query_name = request.get_json()['Query']
            # request is exp id string
            _delete(collection, request)
            response = {
                "Message": "Success"
            }
        except Exception as exception:
            response = {
                'Message': f"Failed: '{exception}' raised"
            }
        return jsonify(response)

    if request.method == 'PUT':
        # Update Data
        data = request.get_json()
        update_payload = dict()

        if "mongo_id" in data:
            query_id = data["mongo_id"]
            del data["mongo_id"]
        else:
            query_id = data["Experience"]

        _set_payload(data, update_payload)

        try:
            _put(collection, update_payload, query_id)
            response = {
                "Message": "Success"
            }

        except Exception as exception:
            response = {
                "Message": f"Failed: {exception} occured"
            }

        return jsonify(response)


@app.route('/api/search', methods=['POST'])
def search_for_experience():
    db = client["Experience"]
    collection = db["Experience"]

    if request.method == 'POST':
        return _search_for_experience(
            collection, request.json, client["User"]["User"]
            )


# GETS EXPERIENCE DETAILS
@app.route(
        '/api/experience-data/<experience_id>',
        methods=['GET', 'PUT', 'DELETE']
        )
def get_experience_by_id(experience_id=None):
    db = client["Experience"]
    collection = db["Experience"]

    try:
        ObjectId(experience_id)  # raise exception if not valid ObjectId
    except Exception as e:
        return jsonify({"Message": f"Invalid ID: {str(e)}"})

    try:
        if request.method == 'GET':
            # Pass experience_id as part of the request body to _get
            filters = {"_id": experience_id}
            experience_data = _get(filters, collection)

            if experience_data:
                experience = experience_data  # Get the first experience
                experience["_id"] = str(experience["_id"])
                response = {
                    "Message": "Success",
                    "data": experience
                }
            else:
                response = {
                    "Message": "Experience not found"
                }
        elif request.method == 'PUT':
            return general_request(request, collection)
        elif request.method == 'DELETE':
            try:
                _delete(collection, experience_id)
                response = {
                    "Message": "Success"
                }
            except Exception as exception:
                response = {
                    'Message': f"Failed: '{exception}' raised"
                }
            return jsonify(response)

    except Exception as e:
        response = {
            "Message": f"Failed: {e} raised"
        }

    return jsonify(response)


@app.route('/api/user-trips/<user_id>', methods=['GET'])
def get_user_trips(user_id):
    db = client["User"]
    user_collection = db["User"]
    trip_collection = client["Trip"]["Trip"]

    try:
        # Ensure user_id is a valid ObjectId
        mongo_user_id = ObjectId(user_id)

        # Fetch user document by MongoDB _id
        user = user_collection.find_one({"_id": mongo_user_id})
        if not user:
            return jsonify({"Message": "User not found", "data": []}), 404

        # Extract trip IDs (stored as strings)
        trip_ids = user.get("Trip", [])

        # Convert trip IDs to ObjectId format
        trip_object_ids = [ObjectId(trip_id) for trip_id in trip_ids]

        # Fetch trips from the Trip collection
        trips = list(trip_collection.find({"_id": {"$in": trip_object_ids}}))

        # Convert ObjectId to string for frontend compatibility
        for trip in trips:
            trip["_id"] = str(trip["_id"])

        return jsonify({"Message": "Success", "data": trips})

    except Exception as e:
        return jsonify({"Message": f"Error: {str(e)}"}), 500


@app.route('/api/experience-data', methods=['POST', 'GET', 'DELETE', 'PUT'])
def experience_request_handler():
    db = client["Experience"]
    collection = db["Experience"]

    return general_request(request, collection)


@app.route('/api/user-data', methods=['GET', 'POST', 'PUT'])
def user_request_handler():

    # Grabs collection DB
    db = client["User"]
    collection = db["User"]

    return general_request(request, collection)


@app.route('/api/user-data/<user_id>', methods=['GET'])
def user_request_handler_by_ID(user_id):

    # Grabs collection DB
    db = client["User"]
    collection = db["User"]

    filters = {"_id": user_id}

    user_data = _get(filters, collection)
    if user_data:
        user = user_data  # Get the first experience
        user["_id"] = str(user["_id"])
        response = {
            "Message": "Success",
            "data": user
        }
    else:
        response = {
            "Message": "Experience not found"
        }
    return jsonify(response)


@app.route('/api/user-experiences/<user_id>', methods=['GET'])
def get_user_experiences(user_id):
    db = client["User"]
    user_collection = db["User"]
    experience_collection = client["Experience"]["Experience"]

    try:
        # Ensure user_id is a valid ObjectId
        mongo_user_id = ObjectId(user_id)

        # Fetch user document by MongoDB _id
        user = user_collection.find_one({"_id": mongo_user_id})
        if not user:
            return jsonify({"Message": "User not found", "data": []}), 404

        # Extract experience IDs (stored as strings)
        experience_ids = user.get("Experience", [])
        bookmark_ids = user.get("Bookmarks", [])

        # Convert experience IDs to ObjectId format
        experience_object_ids = [ObjectId(exp_id) for exp_id in experience_ids]
        bookmark_object_ids = [ObjectId(bm_id) for bm_id in bookmark_ids]

        # Fetch experiences from the Experience collection
        experiences = list(experience_collection.find(
            {"_id": {"$in": experience_object_ids}})
            )
        bookmarks = list(experience_collection.find(
            {"_id": {"$in": bookmark_object_ids}})
            )

        # Convert ObjectId to string for frontend compatibility
        for experience in experiences:
            experience["_id"] = str(experience["_id"])
        for bookmark in bookmarks:
            bookmark["_id"] = str(bookmark["_id"])

        return jsonify(
            {"Message": "Success", "data": [experiences, bookmarks]}
            )

    except Exception as e:
        return jsonify({"Message": f"Error: {str(e)}"}), 500


@app.route('/api/trip-data', methods=['GET', 'POST', 'PUT', 'DELETE'])
@app.route(
    '/api/trip-data/<trip_id>', methods=['GET', 'POST', 'PUT', 'DELETE']
    )  # Added URL for trip_id
def trip_request_handler(trip_id=None):
    db = client["Trip"]
    experience_collection = client["Experience"]["Experience"]

    if request.method == 'POST':
        try:
            return general_request(request, db["Trip"])

        except Exception as e:
            return jsonify({"Message": f"Error: {str(e)}"}), 500

    # Handling the GET method for a specific trip
    if request.method == 'GET':
        try:
            # If trip_id is passed, try to find the specific trip
            if trip_id:
                trip = db["Trip"].find_one({"_id": ObjectId(trip_id)})

                if trip:
                    trip_ids = trip.get("Experience", [])
                    trip_object_ids = [ObjectId(t_id) for t_id in trip_ids]
                    experiences = list(experience_collection.find(
                        {"_id": {"$in": trip_object_ids}})
                        )
                    for experience in experiences:
                        experience["_id"] = str(experience["_id"])
                    trip["_id"] = str(trip["_id"])
                    return jsonify({
                        "Message": "Success",
                        # "trip_id": str(trip["_id"]),
                        "data": [trip, experiences]
                    }), 200
                else:
                    return jsonify({"Message": "Trip not found"}), 404
            else:
                return jsonify({"Message": "Trip ID is required"}), 400

        except Exception as e:
            return jsonify({"Message": f"Error: {str(e)}"}), 500

    # Handle other methods (PUT, DELETE) here if needed
    return jsonify({"Message": "Method Not Allowed"}), 405


@app.route('/api/comment-data', methods=['GET', 'POST', 'PUT', 'DELETE'])
def comment_request_handler():

    db = client["Comment"]
    collection = db["Comment"]

    return general_request(request, collection)


# AI (OPENAI API) RECOMMENDATIONS
@app.route("/get_recommendations", methods=["POST"])
def get_recommendations():
    try:
        data = request.json
        location = data.get("location")
        trip_date = data.get("trip_date")
        travel_group = data.get("travel_group")
        interests = data.get("interests", [])

        # Ensure all required data is present
        if not location or not trip_date or not travel_group or not interests:
            return jsonify({"error": "Missing required fields"}), 400

        # Create prompt for ChatGPT
        prompt = (
            f"I am planning a trip to {location} on {trip_date} with my"
            "{travel_group}.\n"
            f"My interests are {', '.join(interests)}.\n"
            "Can you recommend 3 must-visit places for each category?\n"
            "Return the results in json object following this structure:\n"
            '{"Introduction": "Sample Introduction", "Category 1": ['
            '{"name": "Example name 1", "description": "Example description 1"'
            ', "address": "Example address 1"},'
            '{"name": "Example name 2", "description": "Example description 2"'
            ', "address": "Example address 2"},'
            '{"name": "Example name 3", "description": "Example description 3"'
            ', "address": "Example address 3"}], '
            '"Category 2": etc. etc. }'
        )

        # Call ChatGPT API
        response = openaiclient.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )

        # Extract and return response
        recommendations = response.choices[0].message.content
        return jsonify({"recommendations": recommendations})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ------------------- Photo Storage -------------------
# PHOTO_BUCKET = 'cs467-crowd-sourced-travel-planner-images'


@app.route(
        '/api/experience-data/<experience_id>/photos',
        methods=['POST', 'GET', 'DELETE']
        )
def photo_request_handler(experience_id):
    db = client["Experience"]
    collection = db["Experience"]
    PHOTO_BUCKET = 'cs467-crowd-sourced-travel-planner-images'

    if request.method == 'POST':
        # Add Photo
        try:
            # Get all files in the request
            files = request.files.getlist('file')
            if not files:
                return jsonify({'Error': 'No files sent in request'}), 400
            storage_client = storage.Client()
            bucket = storage_client.get_bucket(PHOTO_BUCKET)
            photo_data_list = []

            for file_obj in files:
                file_name = f"{str(ObjectId())}_{file_obj.filename}"
                blob = bucket.blob(file_name)
                file_obj.seek(0)  # Reset file pointer to the beginning
                blob.upload_from_file(file_obj)
                photo_url = blob.public_url

                # Add the uploaded photo's metadata to the list
                photo_data = {
                    "file_name": file_name,
                    "photo_url": photo_url
                }
                photo_data_list.append(photo_data)

            # Update the experience with the list of photo data
            experience = collection.find_one({"_id": ObjectId(experience_id)})
            if experience:
                collection.update_one(
                    {"_id": ObjectId(experience_id)},
                    {"$push": {"photo_data": {"$each": photo_data_list}}}
                )
                return jsonify({
                    "Message": "Success",
                    "photo_data": photo_data_list}
                )
            else:
                return jsonify({'Error': 'Experience Not Found'}), 404

        except Exception as e:
            return jsonify({"Error": str(e)}), 500

    if request.method == 'GET':
        # Get Data
        try:
            data = request.get_json()
            experience_id = data.get("experience_id")
            # experience_id = request.form.get('experience_id')
            if not experience_id:
                return jsonify({"Error": "Experience ID Required"}), 400

            # experience = collection.find_one({"_id" : experience_id})
            experience = collection.find_one({"_id": ObjectId(experience_id)})
            if experience:
                photo_data = experience.get("photo_data", [])
                photo_urls = [photo["photo_url"] for photo in photo_data]

                if not photo_urls:
                    response = {
                        "message": "No photos found for this experience",
                        "experience_id": ObjectId(experience_id)
                    }
                    return jsonify(response)
                response = {
                    "message": "Success",
                    "experience_id": experience_id,
                    "photo_urls": photo_urls
                }
                return jsonify(response), 200
            else:
                return jsonify({'Error': "Experience Not Found"}), 404

        except Exception as e:
            return jsonify({"Error": str(e)}), 500

    if request.method == 'DELETE':
        # Delete Photo
        try:
            # Get JSON data from the request body
            data = request.get_json()
            experience_id = data.get("experience_id")
            # Get the photo URL to delete
            photo_url_to_delete = data.get('photo_url')

            # Check if both experience_id and photo_url are provided
            if not experience_id or not photo_url_to_delete:
                return jsonify({
                    "Error": "Experience_id and Photo_url are required."
                }), 400

            # Extract the file name from the photo_url
            file_name = photo_url_to_delete.split('/')[-1]

            storage_client = storage.Client()
            bucket = storage_client.get_bucket(PHOTO_BUCKET)

            blob = bucket.blob(file_name)
            if not blob.exists():
                return jsonify({
                    'error': "File not found in Cloud Storage"
                }), 404

            blob.delete()

            # Remove the photo metadata from MongoDB
            result = collection.update_one(
                {"_id": ObjectId(experience_id)},
                {"$pull": {"photo_data": {"photo_url": photo_url_to_delete}}}
            )

            # Check if the experience document was updated successfully
            if result.modified_count > 0:
                response = {
                    "message": "Success: Photo URL Removed",
                    "experience_id": experience_id,
                    "removed_photo_url": photo_url_to_delete
                }
                return jsonify(response), 200
            else:
                return jsonify({
                    'Error':
                    "Experience Not Found or Photo URL not in database"
                }), 404

        except Exception as e:
            return jsonify({"Error": str(e)}), 500

# ------------------- FILTER EXPERIENCES -------------------


@app.route("/api/filter-experiences", methods=["GET"])
def filter_experiences():
    """Filter experiences by creation date and user ID."""
    db = client["Experience"]
    experiences_collection = db["Experience"]

    try:
        # Get query parameters from frontend (user_id, start_date, end_date)
        user_id = request.args.get("User", None)
        start_date_str = request.args.get("start_date", None)
        end_date_str = request.args.get("end_date", None)

        # Prepare the base filter
        filters = {}

        # If a user_id is provided, filter by user_id
        if user_id:
            filters["User"] = user_id

        # Prepare date filters if provided
        if start_date_str:
            filters["creationDate"] = {"$gte": start_date_str}
        if end_date_str:
            filters["creationDate"] = filters.get("creationDate", {})
            filters["creationDate"]["$lte"] = end_date_str

        # Query the database based on the filters
        experiences = experiences_collection.find(filters)

        # Sort by creationDate in descending order (newest first)
        experiences = experiences.sort("creationDate", -1)

        # Serialize the results
        experiences_list = []
        for experience in experiences:
            experience["_id"] = str(experience["_id"])
            experiences_list.append(experience)

        return jsonify(experiences_list)

    except Exception:
        return jsonify({"error": "An error occurred."}), 500


if __name__ == '__main__':
    app.run(debug=True, port=8001)
 