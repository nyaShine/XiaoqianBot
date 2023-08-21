import datetime


def is_time_range_valid(start_time_str, end_time_str):
    now = datetime.datetime.now().time()
    start_time = datetime.datetime.strptime(start_time_str, "%H:%M").time()
    end_time = datetime.datetime.strptime(end_time_str, "%H:%M").time()

    return start_time <= now <= end_time
