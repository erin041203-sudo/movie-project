from flask import Flask, render_template, request
import requests

app = Flask(__name__)

API_KEY = "bf8d8752e8552276db00970a4f4f2f74" \
""
BASE_URL = "https://api.themoviedb.org/3"
IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/movie-search')
def movie_search():
    return render_template('movie_search.html')

@app.route('/search', methods=['POST'])
def search():
    keyword = request.form['keyword']

    url = f"{BASE_URL}/search/movie"
    params = {
        "api_key": API_KEY,
        "query": keyword,
        "language": "ko-KR"
    }

    response = requests.get(url, params=params)
    data = response.json()

    results = data.get("results", [])

    return render_template('search_result.html', results=results, image_base_url=IMAGE_BASE_URL)

@app.route('/movie/<int:movie_id>')
def movie_detail(movie_id):
    url = f"{BASE_URL}/movie/{movie_id}"
    params = {
        "api_key": API_KEY,
        "language": "ko-KR"
    }

    response = requests.get(url, params=params)
    movie = response.json()

    return render_template('movie_detail.html', movie=movie, image_base_url=IMAGE_BASE_URL)

if __name__ == '__main__':
    app.run(debug=True)