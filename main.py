import json
import requests
import uuid
import random


class API:
    def __init__(self, url_base: str, token: str = ""):
        self.token = token
        self.url_base = url_base
        self.headers = {"Content-Type": "application/json"}
        self.html_response: requests.Response = None

    def get_content(self):
        return dict(json.loads(self.html_response.content.decode("utf-8")))

    def get(self, add_to_url: str):
        self.html_response = requests.get(
            self.url_base + add_to_url, headers=self.headers
        )
        if self.html_response.status_code == 200:
            return self.get_content()

    def post(self, add_to_url: str, json_data: dict):
        self.html_response = requests.post(
            self.url_base + add_to_url, json=json_data, headers=self.headers
        )
        if self.html_response.status_code in (200, 201):
            return self.get_content()


class GroupMeAPI(API):
    def __init__(self, token: str):
        super().__init__("https://api.groupme.com/v3", token)
        self.headers["X-Access-Token"] = self.token

    def get_groups(self):
        return self.get("/groups")

    def get_group_id(self, name: str):
        response = self.get_groups()
        if response:
            for group in response["response"]:
                if group["name"] == name:
                    return group["id"]

    def create_bot(self, name: str, group_id: str):
        path = "/bots"
        bot_data = {"bot": {"name": name, "group_id": group_id}}
        return self.post(path, bot_data)

    def destroy_bot(self, bot_id: str):
        return self.post("/bots/destroy", {"bot_id": bot_id})

    def get_bots(self):
        return self.get("/bots")

    def get_bot_id(self, name: str):
        response = self.get_bots()
        if response:
            for bot in response["response"]:
                if bot["name"] == name:
                    return bot["bot_id"]

    def send_message(self, message: str, group_id: str):
        path = f"/groups/{group_id}/messages"
        message_data = {"message": {"source_guid": str(uuid.uuid4()), "text": message}}
        return self.post(path, message_data)


class WeatherAPI(API):
    def __init__(self, token: str):
        super().__init__("https://api.open-meteo.com/v1", token)

    def get_weather(self, lat: float = 39.76, long: float = -105.23):
        latitude = lat
        longitude = long
        daily_params = "weathercode,temperature_2m_max,temperature_2m_min,uv_index_max,precipitation_sum,precipitation_probability_max"
        hourly_params = "relativehumidity_2m"
        return self.get(
            f"/forecast?latitude={latitude}&longitude={longitude}&hourly={hourly_params}&daily={daily_params}&windspeed_unit=mph&precipitation_unit=inch&timezone=America%2FDenver&forecast_days=1"
        )


class OilAPI(API):
    def __init__(self, token: str = ""):
        super().__init__(
            "https://markets.tradingeconomics.com/chart?s=cl1:com&interval=1d&span=1y&securify=new&url=/commodity/crude-oil&AUTH=puk84sm%2BYeMwAcy9lDRy9by%2B3CokTBFHO0IIQAj45ByBvpjfGPbSfyxvGPvbhesN&ohlc=0",
            token,
        )

    def get_oil_price(self):
        return self.get("")["series"][0]["data"][-1]["y"]


class WeatherBot:
    def __init__(
        self,
        group_me_api: GroupMeAPI,
        group_id: str,
        locations: dict[str, tuple[float, float]],
        outfits: list[str],
        songs: list[str],
    ) -> None:
        self.weather_api = WeatherAPI(None)
        self.oil_api = OilAPI(None)
        self.group_me_api = group_me_api
        self.group_id = group_id
        self.locations = locations
        self.outfits = outfits
        self.songs = songs
        self.weather: dict = None

    def parse_weather(self):
        assert self.weather is not None
        daily_data: dict = self.weather["daily"]
        hourly_data: dict = self.weather["hourly"]
        humidity: float = self.avg(list(hourly_data["relativehumidity_2m"]))
        (_, _, max_temp, min_temp, uv_index, precipitation, precipitation_chance) = [
            v[0] for _, v in daily_data.items()
        ]
        return (
            max_temp,
            min_temp,
            uv_index,
            precipitation,
            precipitation_chance,
            humidity,
        )

    def celsius_to_kelvin(self, celsius: float):
        return round(celsius + 273.15, 2)

    def avg(self, arr: list[float]):
        return sum(arr) / len(arr)

    def generate_weather_message(self):
        message = ""
        for name, coords in self.locations.items():
            self.weather = self.weather_api.get_weather(*coords)
            if self.weather:
                (
                    max_temp,
                    min_temp,
                    uv_index,
                    precipitation,
                    precipitation_chance,
                    avg_humidity,
                ) = self.parse_weather()
            message += (
                f"The high in {name} today will be {self.celsius_to_kelvin(max_temp)} Kelvin, "
                + f"with a low of {self.celsius_to_kelvin(min_temp)} Kelvin. "
                + f"The UV index for today is {uv_index}. "
                + f"The chance of precipitation for today is a whopping {precipitation_chance}%, "
                + f"and the average humidity is {int(avg_humidity)}%. "
            )
        return message

    def generate_ootd_message(self):
        random.shuffle(self.outfits)
        return f"The outfit of the day is {self.outfits[0]} "

    def generate_song_message(self):
        random.shuffle(self.songs)
        return f"The song of the day is {self.songs[0]}. "

    def generate_oil_message(self):
        oil_price = self.oil_api.get_oil_price()
        return f"The price of WTI is ${oil_price}. "

    def send_weather(self):
        message = (
            self.generate_weather_message()
            + self.generate_oil_message()
            + self.generate_ootd_message()
            + self.generate_song_message()
            + "RIP graffit."
        )
        self.group_me_api.send_message(
            message,
            self.group_id,
        )


def main():
    groupme = GroupMeAPI("")  # enter api access token between the quotes
    group_id = "96423169"  # = groupme.get_group_id("Test")
    locations = {
        "Golden": (39.76, -105.23),
        "Mindanao": (8.13, 125.13),
        "Auburn": (32.61, -85.49),
    }
    outfits = [
        "a pair of black jeans, red socks, purple shoes, and a brown button-down shirt. Add a sherlock holmes detective hat if you're feeling spicy."
    ]
    songs = ["Mo Bamba - Sheck Wes"]
    weatherbot = WeatherBot(groupme, group_id, locations, outfits, songs)
    weatherbot.send_weather()


main()
