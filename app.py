from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, emit, join_room, leave_room
from aes_crypto import encrypt_aes, decrypt_aes
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = "super_secret_key" # Replace with a strong, randomly generated key
socketio = SocketIO(app) # Initialize SocketIO

# Simple in-memory storage for demo purposes
# In a real app, this would be a database
users = {} # {username: password_hash}
groups = {
    "Nhóm bạn thân": [], # list of usernames
    "Dự án AI": [],
    "Gia đình": [],
    "Công việc": []
}
group_messages = { # {group_name: [{'sender': 'user', 'message': 'hello'}, ...]}
    "Nhóm bạn thân": [],
    "Dự án AI": [],
    "Gia đình": [],
    "Công việc": []
}

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password") # Assuming a password input for real login

        # Simple authentication (for demo: any username is fine, password ignored)
        if username:
            session["username"] = username
            return redirect(url_for("home"))
        else:
            # Handle failed login (e.g., flash message)
            return render_template("login.html", error="Tên đăng nhập không hợp lệ.")
    return render_template("login.html")

@app.route('/home')
def home():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("home.html", username=session["username"])

@app.route('/chat', methods=["GET"])
def chat():
    if "username" not in session:
        return redirect(url_for("login"))
    
    # Get available groups and initial messages for a default group
    current_username = session.get("username")
    available_groups = list(groups.keys())
    
    # For demo, if user is not in any group, add them to a default one for chat to work
    if current_username not in groups.get("Nhóm bạn thân", []) and current_username:
        groups["Nhóm bạn thân"].append(current_username) # Auto-join a default group for demo

    return render_template("chat.html",
                           username=current_username,
                           available_groups=available_groups,
                           initial_messages=group_messages.get("Nhóm bạn thân", []))


# SocketIO event handlers
@socketio.on('connect')
def test_connect():
    print(f'Client {request.sid} connected')
    if "username" in session:
        # Join a default room for now, or fetch user's last active room
        join_room("Nhóm bạn thân") # Example: Auto-join 'Nhóm bạn thân' on connect
        emit('status', {'msg': f'{session["username"]} đã tham gia chat.'}, room="Nhóm bạn thân")

@socketio.on('disconnect')
def test_disconnect():
    print(f'Client {request.sid} disconnected')
    if "username" in session:
        # Leave rooms on disconnect (important for proper room management)
        # In a real app, you'd track which rooms a user is in.
        for group_name in groups: # Simple way to leave all known groups for this demo
             if session["username"] in groups[group_name]:
                 leave_room(group_name)
                 emit('status', {'msg': f'{session["username"]} đã rời chat.'}, room=group_name)


@socketio.on('join')
def on_join(data):
    username = session.get("username")
    room = data['room']
    if username and room in groups:
        if username not in groups[room]:
            groups[room].append(username)
        join_room(room)
        emit('status', {'msg': f'{username} đã tham gia {room}.'}, room=room)
        # Send initial messages for the joined room
        emit('load_messages', {'messages': group_messages.get(room, [])})
    else:
        emit('status', {'msg': f'Không thể tham gia nhóm {room}.'})


@socketio.on('leave')
def on_leave(data):
    username = session.get("username")
    room = data['room']
    if username and room in groups:
        if username in groups[room]:
            groups[room].remove(username)
        leave_room(room)
        emit('status', {'msg': f'{username} đã rời khỏi {room}.'}, room=room)
    else:
        emit('status', {'msg': f'Không thể rời nhóm {room}.'})


@socketio.on('create_group')
def on_create_group(data):
    username = session.get("username")
    new_group_name = data['group_name']
    if username and new_group_name and new_group_name not in groups:
        groups[new_group_name] = [username]
        group_messages[new_group_name] = []
        join_room(new_group_name)
        emit('status', {'msg': f'{username} đã tạo nhóm "{new_group_name}".'})
        emit('group_list_update', {'groups': list(groups.keys())}, broadcast=True) # Notify all clients
        emit('load_messages', {'messages': []}) # No initial messages for a new group
    else:
        emit('status', {'msg': f'Không thể tạo nhóm "{new_group_name}". Tên nhóm có thể đã tồn tại hoặc không hợp lệ.'})


@socketio.on('send_message')
def handle_message(data):
    username = session.get("username")
    message = data['message']
    aes_key = data['key']
    current_room = data['room'] # The room the user is currently in

    if username and message and current_room and current_room in groups:
        encrypted_message = encrypt_aes(message, aes_key)
        # Attempt to decrypt for display purposes, but store encrypted
        try:
            decrypted_message = decrypt_aes(encrypted_message, aes_key)
        except Exception as e:
            decrypted_message = f"[Lỗi giải mã: {e}]" # Fallback for decryption errors

        msg_data = {
            'sender': username,
            'encrypted': encrypted_message,
            'decrypted_display': decrypted_message, # For local user's display, or if key is sent
            'timestamp': f"{datetime.now().hour:02}:{datetime.now().minute:02}"
        }
        group_messages[current_room].append(msg_data) # Store messages in memory

        # Emit the message to everyone in the specific room
        emit('receive_message', msg_data, room=current_room)
    else:
        emit('status', {'msg': 'Gửi tin nhắn thất bại. Vui lòng chọn nhóm và nhập đủ thông tin.'})


if __name__ == '__main__':
    from datetime import datetime
    socketio.run(app, debug=True)