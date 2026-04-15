from flask import Flask, render_template, request, redirect, url_for
from collections import Counter
import requests

app = Flask(__name__)

API_KEY = "bf8d8752e8552276db00970a4f4f2f74"
BASE_URL = "https://api.themoviedb.org/3"
IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"

reviews = [
    {
        "id": 1,
        "movie_title": "서울의 봄",
        "content": "황정민 배우의 연기가 정말 압도적이었습니다. 실화라는 걸 알면서도 손에 땀을 쥐고 봤어요.",
        "date": "2024-01-15"
    },
    {
        "id": 2,
        "movie_title": "기생충",
        "content": "봉준호 감독의 연출이 정말 탁월합니다. 계단 하나하나에 상징이 담겨 있어 볼수록 새로운 영화입니다.",
        "date": "2024-01-10"
    },
    {
        "id": 3,
        "movie_title": "파묘",
        "content": "한국적인 공포와 미스터리가 잘 결합된 작품입니다. 최민식 배우의 존재감이 강렬했습니다.",
        "date": "2024-01-05"
    }
]

open_dictionary_words = [
    {
        "id": 1,
        "word": "레전드",
        "category": "스토리",
        "sentiment": "긍정",
        "count": 2341
    },
    {
        "id": 2,
        "word": "몰입감",
        "category": "몰입도",
        "sentiment": "긍정",
        "count": 1892
    },
    {
        "id": 3,
        "word": "노잼",
        "category": "스토리",
        "sentiment": "부정",
        "count": 1204
    },
    {
        "id": 4,
        "word": "소름",
        "category": "연기",
        "sentiment": "긍정",
        "count": 987
    },
    {
        "id": 5,
        "word": "지루",
        "category": "몰입도",
        "sentiment": "부정",
        "count": 843
    },
    {
        "id": 6,
        "word": "띵작",
        "category": "스토리",
        "sentiment": "긍정",
        "count": 721
    }
]

open_dictionary_requests = [
    {
        "id": 1,
        "word": "밤티",
        "count": 3
    },
    {
        "id": 2,
        "word": "갓벽",
        "count": 7
    },
    {
        "id": 3,
        "word": "띵작",
        "count": 12
    }
]

dummy_popular_movies = [
    {"id": 447365, "title": "범죄도시4", "freshness": "92%", "genre": "액션 / 범죄", "poster_path": None},
    {"id": 99999, "title": "파묘", "freshness": "87%", "genre": "공포 / 미스터리", "poster_path": None},
    {"id": 12345, "title": "서울의 봄", "freshness": "95%", "genre": "드라마 / 역사", "poster_path": None},
    {"id": 1022789, "title": "인사이드 아웃2", "freshness": "88%", "genre": "애니메이션", "poster_path": None},
    {"id": 762509, "title": "듄: 파트2", "freshness": "82%", "genre": "SF / 어드벤처", "poster_path": None}
]

dummy_favorites = [
    {"id": 1165067, "title": "올드보이", "freshness": "90%", "genre": "스릴러", "poster_path": None},
    {"id": 496243, "title": "기생충", "freshness": "97%", "genre": "드라마", "poster_path": None},
    {"id": 786892, "title": "부산행", "freshness": "93%", "genre": "액션", "poster_path": None},
    {"id": 99998, "title": "곡성", "freshness": "85%", "genre": "미스터리", "poster_path": None}
]

dummy_my_reviews = [
    {
        "id": 1,
        "movie_id": 12345,
        "title": "서울의 봄",
        "content": "황정민 배우의 연기가 정말 압도적이었습니다. 실화라는 걸 알면서도 손에 땀을 쥐고 봤어요.",
        "date": "2024-01-15",
        "editing": False
    },
    {
        "id": 2,
        "movie_id": 496243,
        "title": "기생충",
        "content": "봉준호 감독의 연출이 정말 탁월합니다. 계단 하나하나에 상징이 담겨 있어서 볼수록 새로운 영화예요.",
        "date": "2024-01-10",
        "editing": False
    },
    {
        "id": 3,
        "movie_id": 99999,
        "title": "파묘",
        "content": "한국적인 공포와 미스터리가 잘 결합된 작품입니다. 최민식 배우의 존재감이 압도적이었어요.",
        "date": "2024-01-05",
        "editing": False
    }
]

dummy_other_reviews = [
    {
        "name": "남채은",
        "initial": "남",
        "rating": "5.0",
        "date": "2024-01-15",
        "content": "황정민 배우의 연기가 정말 압도적이었습니다. 실화라는 걸 알면서도 손에 땀을 쥐고 봤어요. 역대 최고의 한국 영화 중 하나라고 생각합니다.",
        "helpful": 12
    },
    {
        "name": "익명1",
        "initial": "1",
        "rating": "4.5",
        "date": "2024-01-10",
        "content": "역사를 잘 모르는 상태에서 봤는데도 너무 몰입했어요. 전개 속도가 빠르고 결말이 묵직하게 남습니다.",
        "helpful": 7
    },
    {
        "name": "익명2",
        "initial": "2",
        "rating": "4.0",
        "date": "2024-01-08",
        "content": "후반부로 갈수록 점점 더 긴장감이 올라가는 연출이 훌륭했습니다. 다만 역사를 미리 알고 가면 더 몰입할 수 있을 것 같아요.",
        "helpful": 4
    }
]

def get_category_list():
    return ["전체", "스토리", "연출", "연기", "몰입도", "음악"]

def get_badge_class_for_category(category):
    if category == "스토리":
        return "story"
    if category == "연출":
        return "directing"
    if category == "연기":
        return "acting"
    if category == "몰입도":
        return "immersion"
    if category == "음악":
        return "music"
    return "default"

def get_badge_class_for_sentiment(sentiment):
    if sentiment == "긍정":
        return "positive"
    return "negative"

def enrich_dictionary_items(items):
    enriched = []
    for item in items:
        new_item = item.copy()
        new_item["category_class"] = get_badge_class_for_category(item["category"])
        new_item["sentiment_class"] = get_badge_class_for_sentiment(item["sentiment"])
        enriched.append(new_item)
    return enriched

def get_next_dictionary_request_id():
    if not open_dictionary_requests:
        return 1
    return max(item["id"] for item in open_dictionary_requests) + 1

def get_next_dictionary_word_id():
    if not open_dictionary_words:
        return 1
    return max(item["id"] for item in open_dictionary_words) + 1

def get_recent_registered_words(limit=4):
    sorted_words = sorted(open_dictionary_words, key=lambda x: x["id"], reverse=True)
    return enrich_dictionary_items(sorted_words[:limit])

def get_movie_detail_data(movie_id):
    url = f"{BASE_URL}/movie/{movie_id}"
    params = {
        "api_key": API_KEY,
        "language": "ko-KR"
    }
    try:
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return None

def search_movies_data(keyword):
    url = f"{BASE_URL}/search/movie"
    params = {
        "api_key": API_KEY,
        "query": keyword,
        "language": "ko-KR"
    }
    try:
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data.get("results", [])
    except:
        pass
    return []

@app.route("/")
def home():
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        return redirect(url_for("main"))
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    error = ""
    if request.method == "POST":
        password = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")
        if password != password_confirm:
            error = "비밀번호가 일치하지 않습니다"
        else:
            return redirect(url_for("login"))
    return render_template("register.html", error=error)

@app.route("/main")
def main():
    return render_template(
        "index.html",
        nickname="남채은 님",
        popular_movies=dummy_popular_movies,
        favorite_movies=dummy_favorites,
        image_base_url=IMAGE_BASE_URL
    )

@app.route("/search")
def search():
    keyword = request.args.get("q", "").strip()
    results = []
    if keyword:
        results = search_movies_data(keyword)
    return render_template(
        "search_result.html",
        nickname="남채은 님",
        query=keyword,
        results=results,
        result_count=len(results),
        image_base_url=IMAGE_BASE_URL
    )

@app.route("/movie/<int:movie_id>")
def movie_detail(movie_id):
    movie = get_movie_detail_data(movie_id)
    if not movie:
        title = "서울의 봄" if movie_id == 12345 else "파묘" if movie_id == 99999 else "영화 제목"
        movie = {
            "id": movie_id,
            "title": title,
            "release_date": "2023-11-22",
            "vote_average": 7.9,
            "overview": "1979년 12월 12일, 군사 반란을 막으려는 수도경비사령관과 이를 막으려는 보안사령관의 충돌로 시작된 9시간의 이야기...",
            "poster_path": None,
            "genres": [
                {"name": "드라마"},
                {"name": "역사"},
                {"name": "스릴러"}
            ]
        }
    analysis_mode = request.args.get("analysis", "result")
    return render_template(
        "movie_detail.html",
        nickname="남채은 님",
        movie=movie,
        image_base_url=IMAGE_BASE_URL,
        analysis_mode=analysis_mode,
        other_reviews=dummy_other_reviews
    )

@app.route("/my-reviews")
def my_reviews():
    mode = request.args.get("mode", "")
    edit_id = request.args.get("edit_id", "")
    delete_id = request.args.get("delete_id", "")

    reviews = []
    for review in dummy_my_reviews:
        item = review.copy()
        item["editing"] = str(review["id"]) == edit_id and mode == "edit"
        reviews.append(item)

    delete_review = None
    if mode == "delete" and delete_id:
        for review in reviews:
            if str(review["id"]) == delete_id:
                delete_review = review
                break

    return render_template(
        "my_reviews.html",
        nickname="남채은 님",
        reviews=reviews,
        delete_review=delete_review
    )

@app.route("/movie-search")
def movie_search():
    return redirect(url_for("main"))

@app.route("/dictionary")
def dictionary():
    keyword = request.args.get("q", "").strip()
    selected_category = request.args.get("category", "전체")

    filtered_words = open_dictionary_words[:]

    if selected_category != "전체":
        filtered_words = [item for item in filtered_words if item["category"] == selected_category]

    if keyword:
        filtered_words = [item for item in filtered_words if keyword.lower() in item["word"].lower()]

    filtered_words = sorted(filtered_words, key=lambda x: x["count"], reverse=True)

    enriched_words = enrich_dictionary_items(filtered_words)

    for index, item in enumerate(enriched_words, start=1):
        item["rank"] = index

    return render_template(
        "dictionary.html",
        nickname="남채은 님",
        dictionary_words=enriched_words,
        categories=get_category_list(),
        selected_category=selected_category,
        keyword=keyword
    )

@app.route("/dictionary/request", methods=["GET", "POST"])
def dictionary_request():
    if request.method == "POST":
        word = request.form.get("word", "").strip()

        if word:
            existing_request = None
            for item in open_dictionary_requests:
                if item["word"] == word:
                    existing_request = item
                    break

            if existing_request:
                existing_request["count"] += 1
            else:
                open_dictionary_requests.append(
                    {
                        "id": get_next_dictionary_request_id(),
                        "word": word,
                        "count": 1
                    }
                )

        return redirect(url_for("dictionary_request", submitted="1"))

    submitted = request.args.get("submitted", "")
    return render_template(
        "dictionary_request.html",
        nickname="남채은 님",
        submitted=submitted
    )

@app.route("/admin/dictionary")
def dictionary_admin():
    recent_words = get_recent_registered_words()

    return render_template(
        "dictionary_admin.html",
        pending_requests=open_dictionary_requests,
        recent_words=recent_words,
        pending_count=len(open_dictionary_requests),
        categories=["스토리", "연출", "연기", "몰입도", "음악"]
    )

@app.route("/admin/dictionary/action", methods=["POST"])
def dictionary_admin_action():
    action = request.form.get("action", "").strip()
    request_id = request.form.get("request_id", "").strip()

    if not request_id:
        return redirect(url_for("dictionary_admin"))

    target_request = None
    for item in open_dictionary_requests:
        if str(item["id"]) == request_id:
            target_request = item
            break

    if not target_request:
        return redirect(url_for("dictionary_admin"))

    if action == "approve":
        category = request.form.get("category", "").strip()
        sentiment = request.form.get("sentiment", "").strip()

        if not category or not sentiment:
            return redirect(url_for("dictionary_admin"))

        existing_word = None
        for item in open_dictionary_words:
            if item["word"] == target_request["word"] and item["category"] == category and item["sentiment"] == sentiment:
                existing_word = item
                break

        if existing_word:
            existing_word["count"] += target_request["count"]
        else:
            open_dictionary_words.append(
                {
                    "id": get_next_dictionary_word_id(),
                    "word": target_request["word"],
                    "category": category,
                    "sentiment": sentiment,
                    "count": target_request["count"]
                }
            )

        open_dictionary_requests.remove(target_request)

    elif action == "reject":
        open_dictionary_requests.remove(target_request)

    return redirect(url_for("dictionary_admin"))

if __name__ == "__main__":
    app.run(debug=True)