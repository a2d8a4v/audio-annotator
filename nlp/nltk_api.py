import string
import requests

def call_nltk_api(sentence):
    url = 'http://202.5.252.33:5017'
    payload = {
        "sentence": sentence
    }
    headers = {
        'Content-Type': 'application/json'
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()  # Raise an error for bad status codes
        data = response.json()  # Parse the JSON response
        if data['success'] == False:
            return None
        return data['sentence'].upper()
    except requests.exceptions.RequestException as e:
        print(f"Error calling the API: {e}")
        return None

def remove_punctuation(text):
    return text.translate(str.maketrans('', '', string.punctuation))

if __name__ == "__main__":
    # Example usage
    response_data = call_api("hello world!")
    if response_data:
        print("Response:", response_data)
