from telegram import *
from telegram.ext import *
import json
import datetime
import pytz
import asyncio
from asyncio import *
import nest_asyncio
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import httpx
import os

nest_asyncio.apply()

# Loggers for debugging the code

# import logging
# logging.basicConfig(level=logging.DEBUG,format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# logger = logging.getLogger()

# Telegram bot API
TELEGRAM_API_TOKEN = os.environ.__getitem__("BOT_API")

# Create the Application and pass it your bot's token.
application = Application.builder().token(TELEGRAM_API_TOKEN).build()

term_name = "Spring 2024"

tasks_queue = Queue()

# For Dynamic Programing
account_name_cache = {}
course_name_cache = {}
user_id_cache = {}

# Initialize locks for each cache
account_name_lock = asyncio.Lock()
course_name_lock = asyncio.Lock()
user_id_lock = asyncio.Lock()


# /start
async def start(update: Update, context: CallbackContext):
    """Send a message when the command /start is issued."""

    user_name = update.effective_user.first_name
    # Define the button
    start_button = InlineKeyboardButton("Start", callback_data='who_are_you')
    # Create the markup with the button
    markup = InlineKeyboardMarkup([[start_button]])
    await update.message.reply_text(f'Hi {user_name}! Use this bot to manage your Canvas courses.', reply_markup=markup)


# Asks for who it needs to fetch data
async def ask_who_are_you(update: Update, context: CallbackContext):
    """Provides buttons for usernames, and stores selected button info"""

    query = update.callback_query
    await query.answer()

    buttons = [[InlineKeyboardButton("User 1", callback_data="name_0"),
                InlineKeyboardButton("User 2", callback_data="name_1"),
                InlineKeyboardButton("User 3", callback_data="name_2"),
                InlineKeyboardButton("User 4", callback_data="name_3")],
               [InlineKeyboardButton("User 5", callback_data="name_4"),
                InlineKeyboardButton("User 6", callback_data="name_5"),
                InlineKeyboardButton("User 7", callback_data="name_6"),
                InlineKeyboardButton("User 8", callback_data="name_7")],
               [InlineKeyboardButton("User 9", callback_data="name_8"),
                InlineKeyboardButton("User 10", callback_data="name_9"),
                InlineKeyboardButton("User 11", callback_data="name_10"),
                InlineKeyboardButton("User 12", callback_data="name_11")],
               [InlineKeyboardButton("Doesn't matter, I need for all users", callback_data="all_users"), ]]

    markup = InlineKeyboardMarkup(buttons)
    await query.edit_message_text(text=f"Who are you ?", reply_markup=markup)


# Which type of assignment do we need to explore
async def ask_assignment_type(update: Update, context: CallbackContext):
    """Provides buttons for assignment types of 4 types, each one has some logic
            to filter output. Also, this function stores selected button info """

    query = update.callback_query
    await query.answer()
    selected_name = query.data.split

    buttons = [
        [InlineKeyboardButton("For 24h", callback_data="not_completed_24"),
         InlineKeyboardButton("For 48h", callback_data="not_completed_48")],
        [InlineKeyboardButton("Course Grades", callback_data="course_grade"),
         InlineKeyboardButton("For 1 week", callback_data="not_completed_168")]
    ]

    markup = InlineKeyboardMarkup(buttons)
    await query.edit_message_text(text="""What assignments do you need ?
(It's recommended to choose Not Completed in 24h or 48h, to fetch faster)""", reply_markup=markup)

    context.user_data['selected_name'] = query.data


# Scans json data and handles all the data to python dict
async def load_user_data():
    """Parses json data, and gives it as dictionary to use with python."""

    with open('tokens.json', 'r') as file:
        data = json.load(file)
    return data


# Main function to fetch all the required info for courses
async def handle_assignments_query(update: Optional[Update], context: Optional[CallbackContext],
                                   user_selection="default", assignment_status="default"):
    """This is the main function that runs scheduled tasks and stores info from selected buttons
    to give desired output. Note that if it's automated task it doesn't have update/context"""

    # global counter
    user_data = await load_user_data()

    if update and context:
        query = update.callback_query
        await query.answer()
        await query.message.reply_text("Please wait, processing...")
        assignment_status = query.data
        user_selection = context.user_data.get('selected_name')
    else:
        if assignment_status != "course_grade":
            assignment_status = "not_completed_24"

    assignments_info = ""
    tasks = []

    # Handling the "Doesn't matter, I need all the users" button
    if user_selection == "all_users":

        # Logic to handle 'Doesn't matter' option and iterate over all names
        for name, details in user_data.items():
            if name == "all_users":
                continue
            for account in details['accounts']:
                token = account['token']
                gcc_url = account['gcc_url']
                for course_id in account['course_ids']:
                    tasks.append(asyncio.create_task(giving_output(assignment_status, token, course_id, gcc_url)))
        results = await asyncio.gather(*tasks)
        for info in results:
            assignments_info += info

    # Handling the selected name scenario
    else:
        selected_data = user_data.get(user_selection, {})
        if update and not selected_data:
            await query.message.reply_text(text="Error, User data not found. Type /start to restart the session")
            return

        # Getting courses and assignments
        if selected_data:
            for account in selected_data['accounts']:
                token = account['token']
                gcc_url = account['gcc_url']
                for course_id in account['course_ids']:
                    tasks.append(asyncio.create_task(giving_output(assignment_status, token, course_id, gcc_url)))
        results = await asyncio.gather(*tasks)
        for info in results:
            assignments_info += info

    if update:
        if not assignments_info:
            await query.message.reply_text(text="No assignments found for the selected criteria.")
            return

        header = await output_header(assignment_status)
        assignments_info = f"{header}\n\n" + assignments_info

        # Split the assignments_info into chunks
        chunk_size = 4000  # Maximum message length allowed by Telegram
        chunks = [assignments_info[i:i + chunk_size] for i in range(0, len(assignments_info), chunk_size)]

        # Send each chunk as a separate message
        for chunk in chunks:
            await query.message.reply_text(chunk)
    else:
        if not assignments_info:
            assignments_info = "There are no assignments"

        return assignments_info


async def output_header(status) -> str:
    match status:
        case "course grade":
            return "Here are grades for courses:"
        case "not_completed_24":
            return "Here are assignments for upcoming 24 hours:"
        case "not_completed_48":
            return "Here are assignments for upcoming 2 days:"
        case "not_completed_168":
            return "Here are assignments for upcoming week:"


# Making the output for user
async def giving_output(assignment_status, token, course_id, gcc_url) -> str:
    """Checks whether the assignment is submitted, provides output to the user"""

    # global counter

    if gcc_url:
        base_url = 'https://gcc.instructure.com/api/v1/'
    else:
        base_url = 'https://ilearn.instructure.com/api/v1/'

    assignments = []
    assignments_info = ""
    tasks = []

    # Handling scenarios based on user selection
    match assignment_status:
        case "course_grade":
            assignments_info += f"X) {await get_account_name(token, await get_user_id(term_name, token, base_url), base_url)} - {await get_course_name(term_name, token, course_id, base_url)}:  {await get_course_grade(token, await get_user_id(term_name, token, base_url), course_id, base_url)}\n"

            # counter += 1
            return assignments_info
        case 'not_completed_24':
            hours_limit = 24
        case 'not_completed_48':
            hours_limit = 48
        case 'not_completed_168':
            hours_limit = 168

    now_gmt4 = datetime.datetime.now(pytz.timezone('Asia/Dubai'))  # Get current time in GMT+4
    tasks.append(
        asyncio.create_task(get_assignments_for_course(course_id, token, base_url)))  # Fetching assignments

    results = await asyncio.gather(*tasks)
    for info in results:
        assignments += info

    # Formatting
    if assignments:
        for assignment in assignments:
            due_date = assignment.get('due_at', 'N/A')
            status = 'Completed' if assignment['submission']['workflow_state'] in ['submitted',
                                                                                   'graded'] else 'Not Completed'
            if due_date:
                # Calculate time difference for comparison
                assignment_due_date = datetime.datetime.fromisoformat(due_date[:-1]).replace(
                    tzinfo=pytz.UTC).astimezone(pytz.timezone('Asia/Dubai'))
                time_difference = assignment_due_date - now_gmt4
                if 0 < time_difference.total_seconds() <= hours_limit * 3600 and status == 'Not Completed':
                    assignments_info += f"X) {await get_account_name(token, await get_user_id(term_name, token, base_url), base_url)} - {await get_course_name(term_name, token, course_id, base_url)}: {assignment_due_date.strftime('%B %d, %I:%M %p')}\n"

                    # counter += 1
            else:
                continue  # Skips when assignments' due date is not specified

    else:
        assignments_info = "There are no assignments"

    return assignments_info


# Fetching course name
async def get_course_name(term_name, access_token, course_id, base_url):
    """API call to fetch course name"""

    async with course_name_lock:
        if course_name_cache.get(course_id) is not None:
            return course_name_cache.get(course_id)
        else:
            endpoint = 'courses?include[]=term&per_page=100'
            url = f'{base_url}{endpoint}'
            headers = {'Authorization': f'Bearer {access_token}'}
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get(url, headers=headers)
                    response.raise_for_status()
                    courses = []
                    for course in response.json():
                        if 'term' in course and course['term']['name'] == term_name:
                            courses.append(course)

                    for course in courses:
                        if int(course_id) == course['id']:
                            name = course['name'].split()
                            res = " ".join(name[:2])
                    course_name_cache[course_id] = res
                    return res
                except httpx.HTTPStatusError as e:
                    print(f"Failed to fetch course name: {e}")
                    return "Course name fetch error"


# Fetching User Id
async def get_user_id(term_name, access_token, base_url):
    """API call to fetch user id"""

    async with user_id_lock:
        if user_id_cache.get(access_token) is not None:
            return user_id_cache.get(access_token)
        else:
            endpoint = 'courses?include[]=term&per_page=100'
            url = f'{base_url}{endpoint}'
            headers = {'Authorization': f'Bearer {access_token}'}
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get(url, headers=headers)
                    response.raise_for_status()
                    courses = []
                    for course in response.json():
                        if 'term' in course and course['term']['name'] == term_name:
                            courses.append(course)
                    user_id = courses[0]['enrollments'][0]['user_id']
                    user_id_cache[access_token] = user_id
                    return user_id
                except httpx.HTTPStatusError as e:
                    print(f"Failed to fetch user ID: {e}")
                    return None


# Fetching account name
async def get_account_name(access_token, user_id, base_url):
    """API call to fetch account name"""

    async with account_name_lock:  # Acquire lock before accessing the cache
        if account_name_cache.get(access_token) is not None:
            return account_name_cache.get(access_token)
        else:
            endpoint = f"users/{user_id}"
            url = f'{base_url}{endpoint}'
            headers = {'Authorization': f'Bearer {access_token}'}
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get(url, headers=headers)
                    response.raise_for_status()
                    account_name_cache[access_token] = response.json().get('name')
                    return response.json().get('name')
                except httpx.HTTPStatusError as e:
                    print(f"Failed to fetch account name: {e}")
                    return "Account name fetch error"


# Fetching course grade
async def get_course_grade(access_token, user_id, course_id, base_url):
    """API call to fetch course grade"""

    endpoint = f"courses/{course_id}/enrollments?user_id={user_id}"
    url = f"{base_url}{endpoint}"
    headers = {'Authorization': f'Bearer {access_token}'}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            enrollments = response.json()
            for enrollment in enrollments:
                if enrollment['user_id'] == user_id:
                    return enrollment.get('grades', {}).get('current_score')
            return None
        except httpx.HTTPStatusError as e:
            print(f"Failed to fetch course grade: {e}")
            return None


# Fetching courses
async def get_assignments_for_course(course_id, access_token, base_url):
    """API call to fetch courses"""

    assignments = []
    endpoint = f'courses/{course_id}/assignments?include[]=submission'
    url = f'{base_url}{endpoint}'
    headers = {'Authorization': f'Bearer {access_token}'}

    async with httpx.AsyncClient() as client:
        while url:
            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                all_assignments = response.json()
                # Process assignments...
                assignments.extend(all_assignments)
                links = response.links  # Uses links to fetch all the data carefully
                url = links['next']['url'] if 'next' in links else None
            except httpx.HTTPStatusError as e:
                print(f"Failed to fetch assignments: {e}")
                break
    return assignments


# /help
async def help_command(update, context):
    """Send a message when the command /help is issued."""

    await update.message.reply_text("You don't need any help, Do everything yourself, I believe in you!")


# Replying any other message
async def echo(update, context):
    """Echo the user message."""

    await update.message.reply_text(text="Type /start to make use of my features")


# 1st scheduled task
async def my_async_job():
    """Forwards not submitted assignments that need to be done in 24 hours to each user every day at 9 PM"""

    print("Job is being executed")  # Add this line
    tasks = []
    user_telegram_ids = []

    user_data = await load_user_data()

    # Iterate over each user
    for user_id, details in user_data.items():
        telegram_id = details.get('telegram_id')
        user_name = user_id
        if user_name == "all_users":
            break
        if telegram_id:
            tasks.append(asyncio.create_task(handle_assignments_query(None, None, user_selection=user_name)))
            user_telegram_ids.append(telegram_id)

    results = await asyncio.gather(*tasks)  # Gather results from all tasks

    for i, assignments_info in enumerate(results):
        telegram_id = user_telegram_ids[i]  # Get the corresponding telegram ID
        chunk_size = 4000  # Maximum message length allowed by Telegram
        chunks = [assignments_info[i:i + chunk_size] for i in range(0, len(assignments_info), chunk_size)]

        await application.bot.send_message(chat_id=telegram_id,
                                           text=""" This is automated task!\nHere are your assignments for upcoming 24 hours:\n\n""")

        # Send each chunk as a separate message
        for chunk in chunks:
            await application.bot.send_message(chat_id=telegram_id, text=chunk)


# 2nd scheduled task
async def my_async_job_all_users():
    """Collects same info like 1st task, but for all user and forward it to the root user every day at 11 PM"""

    print("Collecting info for all users...")
    user_data = await load_user_data()
    all_users_info = ""  # String to accumulate all messages
    tasks = []
    orig_names = []

    # Iterate over each user except "all_user"
    for user_id, details in user_data.items():
        if user_id == "all_users":
            continue  # Skip the "all_user" entry
        orig_name = details.get("orig_name", "User")  # Default to "User" if not specified
        telegram_id = details.get("telegram_id")
        if telegram_id:
            tasks.append(asyncio.create_task(handle_assignments_query(None, None, user_selection=user_id)))
            orig_names.append(orig_name)

    results = await asyncio.gather(*tasks)
    for name, assignments_info in enumerate(results):
        all_users_info += f"Info for {orig_names[name]}:\n{assignments_info}\n"  # Append the user's info

    # Send the collected info to the telegram_id specified for "all_user"
    telegram_id_all_users = user_data.get("all_users", {}).get("telegram_id")
    if telegram_id_all_users and all_users_info:
        chunk_size = 4000  # Telegram's max message length
        chunks = [all_users_info[i:i + chunk_size] for i in range(0, len(all_users_info), chunk_size)]

        await application.bot.send_message(chat_id=telegram_id_all_users,
                                           text="This is automated task!\nHere are assignments for all users for upcoming 24 hours:\n\n")

        for chunk in chunks:
            await application.bot.send_message(chat_id=telegram_id_all_users, text=chunk)


# 3nd scheduled task
async def my_async_job_course_grades():
    """Filters courses for all users which grade is below 80%, and forward it to the root user every day at 8 PM"""

    print("Fetching course grades for all users...")
    user_data = await load_user_data()
    grades_info = ""

    for user_id, details in user_data.items():
        if user_id == "all_users":  # Skip the all_users entry
            continue
        # counter = 1  # Initialize counter for each user
        orig_name = details.get("orig_name", "User")  # Default to "User" if not specified

        # Fetch course grades for each user
        user_grades = await handle_assignments_query(None, None, user_selection=user_id,
                                                     assignment_status="course_grade")

        # Initialize a list to store formatted grades below 80.
        below_80_grades = []

        # Process each grade entry.
        grades_list = user_grades.split('\n')
        for grade in grades_list:
            # Split the grade entry to extract the course name and grade value.
            # Assuming the format "Counter) Course Name: Grade Value".
            parts = grade.split(')')
            if len(parts) > 1:
                course_info = parts[1]  # Get the part after the original counter.
                course_name_grade = course_info.split(':')
                if len(course_name_grade) > 1:
                    grade_str = course_name_grade[-1].strip()
                    if grade_str.replace('.', '', 1).isdigit():  # Check if the grade is a number.
                        grade_value = float(grade_str)
                        if grade_value < 80:
                            course_name = course_name_grade[0].strip()
                            below_80_grades.append(f"X) {course_name}: {grade_value}")
                            # counter += 1  # Increment the counter for each course below 80.

        # Add user-specific grades info to the overall message.
        if below_80_grades:
            grades_info += f"User '{orig_name}' has grades below 80 in the following courses:\n" + "\n".join(
                below_80_grades) + "\n\n"
        else:
            grades_info += f"User '{orig_name}' has no courses with grades below 80.\n\n"

    # Send the compiled info to the telegram_id specified for "all_users"
    telegram_id_all_users = user_data.get("all_users", {}).get("telegram_id")
    if telegram_id_all_users and grades_info:
        chunk_size = 4000
        chunks = [grades_info[i:i + chunk_size] for i in range(0, len(grades_info), chunk_size)]

        await application.bot.send_message(chat_id=telegram_id_all_users,
                                           text="This is automated task!\nHere are courses with grades below 80%:\n\n")

        for chunk in chunks:
            await application.bot.send_message(chat_id=telegram_id_all_users, text=chunk)


# Making the order of user requests
async def enqueue_task(update: Update, context: CallbackContext):
    """Puts all the requests in queue, to handle them in parallel """

    await tasks_queue.put((update, context))


# Divides the requests into nodes to handle the in parallel
async def worker_nodes(name, queue):
    """With asynchronous queue and working nodes which rely on compute cores the bot handles requests
                                                                        in parallel simultaneously"""
    print("Worker is starting")
    while True:
        print(f"{name} is being executed")
        # Get a "work item" out of the queue.
        update, context = await queue.get()

        # Simulate a "long" operation based on the command
        await handle_assignments_query(update, context)

        # Notify the queue that the "work item" has been processed.
        queue.task_done()


async def main():
    # Create an AsyncIO scheduler instance
    scheduler = AsyncIOScheduler()

    # Schedule `my_async_job` to run daily at 9:00 AM (GMT+4)
    scheduler.add_job(
        my_async_job,
        CronTrigger(hour=20, minute=0, timezone=pytz.timezone('Asia/Dubai'))
    )

    # Schedule a job to give all the info to the root at 11:00 PM (GMT +4)
    scheduler.add_job(
        my_async_job_all_users,
        CronTrigger(hour=22, minute=0, timezone=pytz.timezone('Asia/Dubai'))
    )

    # Schedule a job to check for course grades below 80 and notify at the desired time
    scheduler.add_job(
        my_async_job_course_grades,
        CronTrigger(hour=22, minute=20, timezone=pytz.timezone('Asia/Dubai'))  # Example: 8 PM every day
    )

    # Start the schedule
    scheduler.start()

    # Create worker tasks to process the queue concurrently.
    workers = []
    for i in range(9):
        workers.append(asyncio.create_task(worker_nodes(f'worker-{i}', tasks_queue)))

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(ask_who_are_you, pattern='^who_are_you$'))
    application.add_handler(CallbackQueryHandler(ask_assignment_type, pattern='^name_'))
    application.add_handler(CallbackQueryHandler(ask_assignment_type, pattern='^all_users$'))
    application.add_handler(CallbackQueryHandler(enqueue_task, pattern='^not_completed.*$'))
    application.add_handler(CallbackQueryHandler(enqueue_task, pattern='^course_grade$'))

    # on noncommand i.e. message - echo the message on Telegram
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    await application.run_polling()

    # Wait for the task queue to be fully processed before exiting
    await tasks_queue.join()

    # Cancel our worker tasks after the queue has been processed
    for worker in workers:
        worker.cancel()
    await asyncio.gather(*workers, return_exceptions=True)


if __name__ == '__main__':
    asyncio.run(main())
