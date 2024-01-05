let API_URL = "http://127.0.0.1:8000/"
const STORAGE_DB_KEY = "sr-db-key"
const STORAGE_CLIENT_USERNAME = "sr-username"
const STORAGE_SESSION_ID = "sr-session-id"
const ROOM_CODE = window.location.hash.substring(1)
let IS_ROOM_ADMIN = false
let notification_buffer = []

function handleApiError(result) {
    console.error("API ERROR: " + result.err_msg)
    if (result.err_msg == "@VALIDATION_FAIL") {
        localStorage.setItem(STORAGE_DB_KEY, '')
        localStorage.setItem(STORAGE_CLIENT_USERNAME, '')
        redirectToLogin()
        alert("Client validation failed... Please relogin.")
        return
    }
    if (result.err_msg == "@ROOM_VALIDATION_FAIL") {
        redirectToDashboard()
        alert("Room validation failed...")
        return
    }
    showError(result.err_msg)
}

function convertBytesToReadableSize(fileSizeInBytes) {
    let i = -1;
    let byteUnits = [' kB', ' MB', ' GB', ' TB'];
    do {
        fileSizeInBytes /= 1024;
        i++;
    } while (fileSizeInBytes > 1024);

    return Math.max(fileSizeInBytes, 0.1).toFixed(1) + byteUnits[i];
}


// Check API server

fetch(API_URL).catch(error => { showError("Server is offline!") })


// Redirects

function redirectToDashboard() { window.location = "dashboard.html" }
function redirectToLogin() { window.location = "index.html" }
function redirectToRoomView(code) { window.location = "roomview.html#" + code }


// Notification triggers

function showError(message) {
    butterup.toast({
        title: 'Error 🚨',
        icon: false,
        type: 'error',
        message: message,
        dismissable: true,
        location: 'bottom-right',
    });
}

function showSuccess(message) {
    butterup.toast({
        title: 'Success ✅',
        icon: false,
        type: 'success',
        message: message,
        dismissable: true,
        location: 'bottom-right',
    });
}

function showInfo(message) {
    butterup.toast({
        title: 'Info ☝️',
        icon: false,
        type: 'info',
        message: message,
        dismissable: true,
        location: 'bottom-right',
    });
}

function showWarning(message) {
    butterup.toast({
        title: 'Warning ⚠️',
        icon: false,
        type: 'warning',
        message: message,
        dismissable: true,
        location: 'bottom-right',
    });
}


// Storage getters

function getSavedDbKey() {
    return localStorage.getItem(STORAGE_DB_KEY)
}

function getSavedSessionId() {
    return localStorage.getItem(STORAGE_SESSION_ID)
}

function grabAuthData() {
    return {
        db_key: getSavedDbKey(),
        session_id: getSavedSessionId()
    }
}

function getSavedUsername() {
    return localStorage.getItem(STORAGE_CLIENT_USERNAME)
}

// Website structure modifiers

function isRoomActive(code) {
    const container = document.getElementsByClassName("active-rooms-container")[0]
    let children = Array.from(container.childNodes)
    let found = false;
    children.forEach(element => {
        if (element.id == code) {
            found = true;
        }
    });

    return found
}

function appendActiveRoom(name, code, isadmin=false) {
    const container = document.getElementsByClassName("active-rooms-container")[0]

    if (isRoomActive(code)) {
        console.error("Cannot append room: " + code + " (already active)")
        return false
    }

    let room_div = document.createElement("div")
    room_div.id = code
    room_div.className = "active-room"

    if (isadmin) {
        let admin_badge_container = document.createElement("div")
        admin_badge_container.className = "admin-badge-container"
        admin_badge_container.innerHTML = `<div class="admin-badge"><i class="fa-solid fa-crown"></i></div>`
        room_div.appendChild(admin_badge_container)
    }

    let notification_badge_container = document.createElement("div")
    notification_badge_container.className = "notification-badge-container"
    notification_badge_container.setAttribute("state", "false")
    notification_badge_container.innerHTML = `<div class="notification-badge"></div>`
    room_div.appendChild(notification_badge_container)

    let title_tag = document.createElement("h2")
    title_tag.className = "room-title"
    title_tag.innerHTML = name
    room_div.appendChild(title_tag)

    let action_group = document.createElement("div")
    action_group.className = "room-action-group"
    room_div.appendChild(action_group)

    let open_btn = document.createElement("button")
    open_btn.className = "open-room"
    open_btn.innerHTML = "Join"
    open_btn.setAttribute("onclick", "redirectToRoomView('" + code + "')")
    action_group.appendChild(open_btn)
    
    let leave_btn = document.createElement("button")
    leave_btn.className = "leave-room"
    leave_btn.innerHTML = '<i class="fa-solid fa-arrow-right-from-bracket fa-xs"></i>'
    leave_btn.setAttribute("onclick", "sendLeaveRoomRequest('" + code + "')")
    action_group.appendChild(leave_btn)

    container.appendChild(room_div)
}

function removeActiveRoom(code) {
    try {
        document.getElementById(code).remove()
    } catch (error) {
        
    }
}

function isFileOnList(fileid) {
    const container = document.getElementsByClassName("filesContainer")[0]
    let children = Array.from(container.childNodes)
    let found = false;
    children.forEach(element => {
        if (element.id == fileid) {
            found = true;
        }
    });

    return found
}

function appendFile(name, author, size, fileid) {
    const container = document.getElementsByClassName("filesContainer")[0]

    if (isFileOnList(fileid)) {
        console.error("cannot append file: " + name + " id: " + fileid + " (currently on list)")
        return
    }

    let file_div = document.createElement("div")
    file_div.className = "file"
    file_div.id = fileid

    let file_name = document.createElement("h4")
    file_name.className = "fileName"
    file_name.innerHTML = name
    file_div.appendChild(file_name)

    let file_author = document.createElement("p")
    file_author.className = "fileField"
    file_author.innerHTML = "Author: "
    file_div.appendChild(file_author)

    let file_author_value = document.createElement("span")
    file_author_value.className = "fileValue fileAuthor"
    file_author_value.innerHTML = author
    file_author.appendChild(file_author_value)

    let file_size = document.createElement("p")
    file_size.className = "fileField"
    file_size.innerHTML = "Size: "
    file_div.appendChild(file_size)

    let file_size_value = document.createElement("span")
    file_size_value.classList = ["fileValue", "fileSize"]
    file_size_value.innerHTML = size
    file_size.appendChild(file_size_value)

    let action_group = document.createElement("div")
    action_group.className = "fileActionGroup"

    let download_file = document.createElement("button")
    download_file.className = "downloadFile"
    download_file.innerHTML = "Download"
    download_file.setAttribute("onclick", "sendDownloadFileRequest('" + fileid + "')")
    action_group.appendChild(download_file)
    
    if (IS_ROOM_ADMIN) {
        let remove_file = document.createElement("button")
        remove_file.className = "removeFile"
        remove_file.setAttribute("onclick", "sendRemoveFileRequest('" + fileid + "')")
        remove_file.innerHTML = `<i class="fa-solid fa-trash fa-xs"></i>`
        action_group.appendChild(remove_file)
    }

    file_div.appendChild(action_group)
    container.appendChild(file_div)
}

function removeFile(fileid) {
    document.getElementById(fileid).remove()
}

function appendMember(username, isadmin=false) {
    const members_container = document.getElementsByClassName("usersContainer")[0]

    let member_view = document.createElement("div")
    member_view.className = "memberView"
    member_view.id = "user-" + username
    member_view.setAttribute("onclick", 'kickMember("' + username + '")')

    if (isadmin) {
        let admin_badge = document.createElement("div")
        admin_badge.className = "member-admin-badge"
        admin_badge.innerHTML = `<i class="fa-solid fa-crown fa-xs"></i>`
        member_view.appendChild(admin_badge)
    }

    let member_name = document.createElement("h2")
    member_name.className = "memberName"
    member_name.innerHTML = username
    
    member_view.appendChild(member_name)
    members_container.appendChild(member_view)

    const amount_element = document.getElementById("membersAmount")
    let values = amount_element.innerHTML.split("/")
    amount_element.innerHTML = parseInt(values[0]) + 1 + "/" + values[1]
}

function removeMember(username) {
    document.getElementById("user-" + username).remove()

    const amount_element = document.getElementById("membersAmount")
    let values = amount_element.innerHTML.split("/")
    amount_element.innerHTML = parseInt(values[0]) - 1 + "/" + values[1]
}

function appendMessage(author, content) {
    const msgContainer = document.getElementsByClassName("msgContainer")[0]

    if (content.trim().length == 0) {
        console.warn("Not appending message from: " + author + " (blank content)")
        return
    }

    let msg_div = document.createElement("div")
    msg_div.className = "msg"

    let msg_author = document.createElement("h4")
    msg_author.className = "msgAuthor"
    msg_author.innerHTML = author

    let msg_content = document.createElement("p")
    msg_content.className = "msgContent"
    msg_content.innerHTML = content

    msg_div.appendChild(msg_author)
    msg_div.appendChild(msg_content)
    msgContainer.appendChild(msg_div)

    scrollToMessagesBottom()
}

function setRoomNotificationState(code, state) {
    try {
        let room_container = document.getElementById(code)
        let badge_container = room_container.querySelector(".notification-badge-container")
        badge_container.setAttribute("state", state)
        console.log("Changed notification state for: " + code + " to: " + state)
    } catch (error) {
        console.log("Received notifcation message, but room is not loaded yet. Saving code in buffer: " + code)
        notification_buffer.push(code)
    }
}


// Setups

function setupNotificationWS() {
    let ws = new WebSocket(API_URL.replaceAll("http", "ws").replaceAll("https", "ws") + "rooms/notificationServer/" + getSavedDbKey())
    ws.onmessage = function (ev) {
        handleNotificationWSMessage(ev.data)
        ev.preventDefault()
    }
    console.log("Connected to notificationServer")

}

function handleNotificationWSMessage(content) {
    content = JSON.parse(content.replaceAll("'", '"'))
    console.log("Received message from NotificationServer: " + content.status)

    switch (content.status) {
        case "ROOM_NOTIFICATION":
            setRoomNotificationState(content.room_code, true)
            break

        case "RM_ROOM":
            removeActiveRoom(content.room_code)
            showWarning("Room: " + content.room_name + " just has been removed.")
            break

        case "ROOM_KICK":
            removeActiveRoom(content.room_code)
            showWarning("You were kicked from room: " + content.room_name)
            break
    }
}

function setupRoomWS(room_key) {
    let ws = new WebSocket(API_URL.replaceAll("http", "ws").replaceAll("https", "ws") + "rooms/room_ws/" + room_key)
    ws.onmessage = function (ev) {
        handleRoomWSMessage(ev.data)
        ev.preventDefault()
    }
    console.log("Connected to room_ws")
}

function handleRoomWSMessage(content) {
    content = JSON.parse(content.replaceAll("'", '"'))
    console.log("Received message from RoomWS: " + content.status)

    data = content.data

    switch (content.status) {
        case "ADD_MSG":
            author = data.author
            msg_content = data.content
            appendMessage(author, msg_content)
            break

        case "UPDATE_LOCK_STATE":
            state = data.state
            document.getElementById("room-is-locked").innerHTML = Boolean(state) ? "Yes" : "No"
            document.getElementsByTagName("body")[0].setAttribute("lock-state", Boolean(state) ? "true" : "false")
            break

        case "ADD_FILE":
            author = data.author
            fileid = data.fileid
            filename = data.name
            size = convertBytesToReadableSize(data.size)
            appendFile(filename, author, size, fileid)
            break

        case "USER_JOIN":
            username = data.username
            appendMember(username)
            showInfo(username + " joined the room")
            break

        case "USER_LEFT":
            username = data.username
            removeMember(username)
            showInfo(username + " left the room")
            break

        case "RM_ROOM":
            code = data.room_code
            console.warn("Received RM_ROOM for room: " + code)
            redirectToDashboard()
            removeActiveRoom(code)
            break

        case "KICK_MEMBER":
            username = data.username
            showWarning(username + " has just been kicked.")
            removeMember(username)

            if (username == getSavedUsername()) {
                alert("You have been kicked from this room...")
                redirectToDashboard()
            }
            break

        case "RM_FILE":
            fileid = data.fileid
            removeFile(fileid)
            break
    }

    console.log("| status: " + content.status)
}

function loadUserData() {
    const options = {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(grabAuthData())
    }

    fetch(API_URL + "accounts/userData/", options)
        .then(response => response.json())
        .then(result => {
            console.log('Received response from USERDATA request', result);
            switch (result.status) {
                case true:
                    let username = result.data.username
                    document.getElementById("username").innerHTML = username
                    localStorage.setItem(STORAGE_CLIENT_USERNAME, username)

                    let joined_at = result.data.joined_at
                    document.getElementById("joined_at").innerHTML = joined_at

                    for (const [room_code, room_obj] of Object.entries(result.data.rooms)) {
                        appendActiveRoom(room_obj.name, room_code, room_obj.is_admin)
                        if (notification_buffer.includes(room_code)) {
                            setRoomNotificationState(room_code, true)
                        }
                    }
                    break

                case false:
                    handleApiError(result)
                    localStorage.setItem(STORAGE_DB_KEY, '')
                    localStorage.setItem(STORAGE_CLIENT_USERNAME, '')
                    redirectToLogin()
                    break
            }
        })
        .catch(error => {
            console.error('Error while sending USERDATA request', error);
            showError("Cannot load user's data.")
        });

}

function connectWithRoom() {
    if (ROOM_CODE == "") {
        console.error("Blank room code found")
        redirectToDashboard()
    }

    let data = {
        room_code: ROOM_CODE
    }

    data = Object.assign(grabAuthData(), data)

    const options = {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    }

    fetch(API_URL + "rooms/connect", options)
        .then(response => response.json())
        .then(result => {
            console.log('Received response from CONNECT request', result);
            switch (result.status) {
                case true:
                    let room_key = result.room_key
                    IS_ROOM_ADMIN = result.is_admin
                    if (IS_ROOM_ADMIN) {
                        document.getElementsByTagName("body")[0].setAttribute("is-admin", "true")
                    }

                    setupRoomWS(room_key)
                    loadRoomData(room_key)
                    break

                case false:
                    handleApiError(result)
                    break
            }
        })
        .catch(error => {
            console.error('Error while sending CONNECT request', error);
            showError("Cannot connect with this room.")
        });
}

function loadRoomData(room_key) {
    const options = {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json'
        }
    }

    fetch(API_URL + "rooms/roomData/" + room_key, options)
        .then(response => response.json())
        .then(result => {
            console.log('Received response from ROOMDATA request', result);
            switch (result.status) {
                case true:
                    const data = result.data
                    document.getElementById("room-name").innerHTML = data.name
                    document.getElementById("room-code").innerHTML = ROOM_CODE
                    document.getElementById("room-creator").innerHTML = data.creator
                    document.getElementById("room-created-at").innerHTML = data.date_created
                    document.getElementById("room-is-pwd").innerHTML = data.is_password? "Yes" : "No"
                    document.getElementById("room-is-locked").innerHTML = data.is_locked? "Yes" : "No"

                    const admin_name = data.admin_username
                    appendMember(admin_name, true)

                    const members = data.members
                    members.forEach(username => {
                        appendMember(username)
                    });

                    const files = data.files
                    for (const fileid in files) {
                        let name = files[fileid].name
                        let author = files[fileid].author
                        let size = files[fileid].size
                        size = convertBytesToReadableSize(size)

                        appendFile(name, author, size, fileid)
                    }

                    const messages = data.messages
                    for (const msg_id in messages) {
                        let author = messages[msg_id].author
                        let content = messages[msg_id].content

                        appendMessage(author, content)
                    }

                    let members_amount = (members.length+1) + "/" + data.max_users
                    document.getElementById("membersAmount").innerHTML = members_amount

                    let lock_state = data.is_locked ? "true" : "false"
                    document.getElementsByTagName("body")[0].setAttribute("lock-state", lock_state)


                    break

                case false:
                    handleApiError(result)
                    showError("Cannot load room's data.")
                    break
            }
        })
        .catch(error => {
            console.error('Error while sending ROOMDATA request', error);
        });
}

function setupFilesDrop() {
    document.getElementById("actualAddFileBtn").onclick = function () {
        const button_element = document.getElementById("fakeAddFileBtn")
        button_element.click()
    }

    document.getElementById("fakeAddFileBtn").onchange = function () {
        let file = document.getElementById("fakeAddFileBtn").files[0]
        uploadFile(file)
    }

    let dropArea = document.getElementById('filesPanel')
    dropArea.ondragover = dropArea.ondragenter = function (evt) {
        evt.preventDefault()
        dropArea.setAttribute("dropstate", "true")
    }

    dropArea.ondragleave = function (evt) {
        evt.preventDefault()
        setTimeout(() => { dropArea.setAttribute("dropstate", "false") }, 1000)
    }

    dropArea.ondrop = function (evt) {
        evt.preventDefault()
        let file = evt.dataTransfer.files[0]
        uploadFile(file)
        dropArea.setAttribute("dropstate", "false")
    }
}

function scrollToMessagesBottom() {
    const msgContainer = document.getElementsByClassName("msgContainer")[0]
    msgContainer.scrollTop = msgContainer.scrollHeight
}


// Forms

function validateName(element) {
    let value = element.value
    if (value.length == 0) {
        element.setAttribute("state", "none")
        return false
    }

    if (value.length < 5 || value.length > 16) {
        element.setAttribute("state", "invalid")
        return false
    }

    element.setAttribute("state", "none")
    return true
}

function validatePassword(element) {
    let value = element.value

    if (value.length == 0) {
        element.setAttribute("state", "none")
        return false
    }

    if (value.length < 5) {
        element.setAttribute("state", "invalid")
        return false
    }

    element.setAttribute("state", "none")
    return true
}


// - index.html
const LoginForm = {
    validateUsername() {
        const element = document.getElementById("login-username")
        return validateName(element)
    },

    validatePassword() {
        const element = document.getElementById("login-password")
        return validatePassword(element)
    },

    validateForm() {
        return this.validateUsername() && this.validatePassword()
    },

    sendRequest(e) {
        e.preventDefault()

        if (!LoginForm.validateForm()) {
            return false;
        }

        const username = document.getElementById("login-username").value
        const password = document.getElementById("login-password").value

        const data = {
            username: username,
            password: password
        };

        const options = {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        };

        fetch(API_URL + "accounts/login", options)
            .then(response => response.json())
            .then(result => {
                console.log('Received response from LOGIN request');
                switch (result.status) {
                    case true:
                        let db_key = result.db_key
                        console.log("session-id: ", result.session_id)
                        localStorage.setItem(STORAGE_DB_KEY, db_key)
                        localStorage.setItem(STORAGE_SESSION_ID, result.session_id)

                        redirectToDashboard()
                        break

                    case false:
                        handleApiError(result)
                        break
                }
            })
            .catch(error => {
                console.error('Error while sending LOGIN request', error);
                showError("Cannot login.")
            });

        return false
    }
}

const RegisterForm = {
    validateUsername() {
        const element = document.getElementById("register-username")
        return validateName(element)
    },

    validateMainPassword() {
        const element = document.getElementById("register-password-main")
        return validatePassword(element)
    },

    validateBothPasswords() {
        const second_element = document.getElementById("register-password-second")
        if (!this.validateMainPassword()) {
            second_element.setAttribute("state", "none")
            return false
        }

        let second_value = second_element.value

        if (second_value.length == 0) {
            second_element.setAttribute("state", "none")
            return false
        }

        if (document.getElementById("register-password-main").value != second_value) {
            second_element.setAttribute("state", "invalid")
            return false
        }

        second_element.setAttribute("state", "none")
        return true
    },

    validateForm() {
        return this.validateUsername() && this.validateBothPasswords()
    },

    sendRequest(e) {
        e.preventDefault()
        if (!this.validateForm()) {
            return false
        }

        const username = document.getElementById("register-username").value
        const password = document.getElementById("register-password-main").value

        const data = {
            username: username,
            password: password
        };

        const options = {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        };

        fetch(API_URL + "accounts/create", options)
            .then(response => response.json())
            .then(result => {
                console.log('Received response from REGISTER request');
                switch (result.status) {
                    case true:
                        let db_key = result.db_key
                        localStorage.setItem(STORAGE_DB_KEY, db_key)
                        localStorage.setItem(STORAGE_CLIENT_USERNAME, username)
                        showSuccess("Account created. Please login...")
                        break

                    case false:
                        handleApiError(result)
                        break
                }
            })
            .catch(error => {
                console.error('Error while sending REGISTER request', error);
                showError("Cannot register.")
            });

        return false
    }
}


// - dashboard.html
const ChpwdForm = {
    validateCurrentPassword() {
        const element = document.getElementById("chpwd-current")
        return validatePassword(element)
    },

    validateNewMainPassword() {
        const element = document.getElementById("chpwd-new-main")
        return validatePassword(element)
    },

    validateForm() {
        return this.validateCurrentPassword()
        && getSavedDbKey() != null
    },

    sendRequest(e) {
        e.preventDefault()
        if (!this.validateForm()) {
            return false
        }
        const current = document.getElementById("chpwd-current").value
        const new_pwd = document.getElementById("chpwd-new-main").value

        const data = {
            db_key: getSavedDbKey(),
            session_id: getSavedSessionId(),
            current: current,
            new: new_pwd
        };

        const options = {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        };

        fetch(API_URL + "accounts/changePassword", options)
            .then(response => response.json())
            .then(result => {
                console.log('Received response from CHPWD request');
                switch (result.status) {
                    case true:
                        showSuccess("Password changed")
                        break

                    case false:
                        handleApiError(result)
                        break
                }
            })
            .catch(error => {
                console.error('Error while sending CHPWD request', error);
                showError("Cannot change password.")
            });
        return false
    }
}

const DeleteAccountForm = {
    validatePassword() {
        const element = document.getElementById("deleteaccount-pwd")
        return validatePassword(element)
    },

    sendRequest(e) {
        e.preventDefault()
        if (!this.validatePassword()) {
            return false
        }

        const password = document.getElementById("deleteaccount-pwd").value

        const data = {
            db_key: getSavedDbKey(),
            session_id: getSavedSessionId(),
            password: password,
        };

        const options = {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        };

        fetch(API_URL + "accounts/delete", options)
            .then(response => response.json())
            .then(result => {
                console.log('Received response from DELETE request');
                switch (result.status) {
                    case true:
                        localStorage.clear()
                        redirectToLogin()
                        break

                    case false:
                        handleApiError(result)
                        break
                }
            })
            .catch(error => {
                console.error('Error while sending DELETE request', error);
                showError("Cannot delete account.")
            });

        return false
    }
}

const JoinRoomForm = {
    validateCode() {
        const element = document.getElementById("joinroom-code")
        let value = element.value
        if (value.length == 0) {
            element.setAttribute("state", "none")
            return false
        }
        if (value.length != 6) {
            element.setAttribute("state", "invalid")
            return false
        }
        element.setAttribute("state", "none")
        return true
    },

    sendRequest(e) {
        e.preventDefault()
        if (!this.validateCode()) {
            return false
        }

        const code = document.getElementById("joinroom-code").value
        let password = document.getElementById("joinroom-pwd").value

        if (isRoomActive(code)) {
            showWarning("You are already member of this room.")
            return false
        }

        if (password == "") {
            password = null
        }

        let data = {
            room_code: code,
            password: password,
        };

        data = Object.assign(grabAuthData(), data)

        const options = {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        };

        fetch(API_URL + "rooms/joinRoom", options)
            .then(response => response.json())
            .then(result => {
                console.log('Received response from JOINROOM request');
                switch (result.status) {
                    case true:
                        room_name = result.name
                        appendActiveRoom(room_name, code)
                        showSuccess("Joined room: " + room_name)
                        break

                    case false:
                        handleApiError(result)
                        break
                }
            })
            .catch(error => {
                console.error('Error while sending JOINROOM request', error);
                showError("Cannot join room.")
            });

        return false
    }
}

const CreateRoomForm = {
    validateName() {
        const element = document.getElementById("createroom-name")
        return validateName(element)
    },

    sendRequest(e) {
        e.preventDefault()

        if (!this.validateName()) {
            return false
        }

        const name = document.getElementById("createroom-name").value
        const maxusers = parseInt(document.getElementById("createroom-maxusers").value)
        let password = document.getElementById("createroom-pwd").value
        if (password == "") {
            password = null
        }

        const data = {
            db_key: getSavedDbKey(),
            session_id: getSavedSessionId(),
            name: name,
            max_users: maxusers,
            password: password
        };

        const options = {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        };

        fetch(API_URL + "rooms/create", options)
            .then(response => response.json())
            .then(result => {
                console.log('Received response from CREATEROOM request');
                switch (result.status) {
                    case true:
                        let code = result.code
                        showSuccess("Created room!")
                        showInfo("Room code: " + code)
                        appendActiveRoom(name, code, true)
                        break

                    case false:
                        handleApiError(result)
                        break
                }
            })
            .catch(error => {
                console.error('Error while sending CREATEROOM request', error);
                showError("Cannot create room.")
            });

        return false

    }
}

const LogoutForm = {
    sendRequest() {
        const options = {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(grabAuthData())
        };
        
        fetch(API_URL + "accounts/logout", options)
            .then(response => response.json())
            .then(result => {
                console.log('Received response from LOGOUT request')
            })
            .catch(error => {
                console.error('Error while sending LOGOUT request', error);
            });

        localStorage.setItem(STORAGE_DB_KEY, '')
        localStorage.setItem(STORAGE_CLIENT_USERNAME, '')
        redirectToLogin()

        return false
    }
}

// const AddFriend = {
//     validateUsername() {
//         const element = document.getElementById("addfriend-name")
//         return validateName(element)
//     },

//     sendRequest(e) {
//         e.preventDefault()
//         if (!this.validateUsername()) {
//             return
//         }

//         let username = document.getElementById("addfriend-name").value

//         let data = {
//             username: username,
//         };

//         data = Object.assign(grabAuthData(), data)

//         const options = {
//             method: 'POST',
//             headers: {
//                 'Content-Type': 'application/json'
//             },
//             body: JSON.stringify(data)
//         };

//         fetch(API_URL + "accounts/sendFriendRequest", options)
//             .then(response => response.json())
//             .then(result => {
//                 console.log('Received response from SENDFRIENDREQUEST request')

//                 switch (result.status) {
//                     case true:
//                         showSuccess("Sent friend request to: " + username)
//                         break

//                     case false:
//                         handleApiError(result)
//                         break
//                 }

//             })
//             .catch(error => {
//                 console.error('Error while sending SENDFRIENDREQUEST request', error);
//             });

//     }    

// }


// - roomview.html
const SendMessageForm = {
    validateContent() {
        const element = document.getElementById("newMsgInput")
        if (element.value.length == 0) {
            element.setAttribute("state", "none")
            return false
        }
        if (element.value.trim().length == 0 || element.value.length > 1024) {
            element.setAttribute("state", "invalid")
            return false
        }

        element.setAttribute("state", "none")
        return true
    },

    sendRequest() {
        if (!this.validateContent()) {
            return false
        }

        const content = document.getElementById("newMsgInput").value

        const data = {
            db_key: getSavedDbKey(),
            session_id: getSavedSessionId(),
            room_code: ROOM_CODE,
            content: content
        }

        const options = {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        };

        fetch(API_URL + "rooms/addMessage", options)
            .then(response => response.json())
            .then(result => {
                console.log('Received response from ADDMESSAGE request')
                document.getElementById("newMsgInput").value = ""

                switch (result.status) {
                    case false:
                        handleApiError(result)
                        break
                }
            })
            .catch(error => {
                console.error('Error while sending ADDMESSAGE request', error);
                showError("Cannot send message.")
            });

        return false

    }
}

function uploadFile(file){
    const formData = new FormData();
    formData.append('db_key', getSavedDbKey());
    formData.append('session_id', getSavedSessionId());
    formData.append('room_code', ROOM_CODE);
    formData.append('file', file);

    fetch(API_URL + 'rooms/uploadFile', {
        method: 'POST',
        body: formData,
        headers: {
            'Accept': 'application/json',
        },
    })
    .then(response => response.json())
    .then(result => {
        console.log('Received response from UPLOADFILE request');
        switch (result.status) {
            case true:
                showSuccess('File uploaded!');
                break;

            case false:
                handleApiError(result);
                break;
        }
    })
    .catch(error => {
        console.error('Error while sending UPLOADFILE request', error);
        showError("Cannot upload file")
    });

    return false

}

function sendDownloadFileRequest(fileid) {

    let data = {
        room_code: ROOM_CODE,
        fileid: fileid
    };

    data = Object.assign(grabAuthData(), data)

    const options = {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    };

    fetch(API_URL + "rooms/downloadFile", options)
        .then(response => {
            if (response.ok) { return response.blob() }
            return response.json().then(result => {
                handleApiError(result)
                return
            })
        })
        .then(result => {            
            console.log('Received response from DOWNLOADFILE request');
            const anchor = document.createElement('a');
            anchor.href = URL.createObjectURL(result);
            anchor.download = getFilename(fileid);
            anchor.click();
            URL.revokeObjectURL(anchor.href);

        })
        .catch(error => {
            console.error('Error while sending DOWNLOADFILE request', error);
        });

    function getFilename(fileid) {
        const filediv = document.getElementById(fileid)
        let children = Array.from(filediv.childNodes)
        let name = "name"
        children.forEach(element => {
            if (element.className == "fileName") {
                name = element.innerHTML
            }
        });
        return name
    }

}

function sendLeaveRoomRequest(code=false) {
    if (code === false) {
        code = ROOM_CODE
    }

    removeActiveRoom(code)

    let data = {
        room_code: code,
    };

    data = Object.assign(grabAuthData(), data)

    const options = {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    };

    fetch(API_URL + "rooms/leaveRoom", options)
        .then(response => response.json())
        .then(result => {
            console.log('Received response from LEAVEROOM request');
            switch (result.status) {
                case true:
                    showInfo("Left room: " + code)
                    redirectToDashboard()
                    break

                case false:
                    handleApiError(result)
                    break
            }
        })
        .catch(error => {
            console.error('Error while sending LEAVEROOM request', error);
            showError("Cannot leave room.")
        });
}

// - roomview.html - admin
function kickMember(username) {
    if (!IS_ROOM_ADMIN) { return }
    if (getSavedUsername() == username) { return }
    
    let data = {
        room_code: ROOM_CODE,
        member_name: username
    };

    data = Object.assign(grabAuthData(), data)

    const options = {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    };

    fetch(API_URL + "rooms/admin/kickMember", options)
        .then(response => response.json())
        .then(result => {
            console.log('Received response from KICKMEMBER request');
            switch (result.status) {
                case true:
                    showInfo("Kicked: " + username)
                    break

                case false:
                    handleApiError(result)
                    break
            }
        })
        .catch(error => {
            console.error('Error while sending KICKMEMBER request', error);
            showError("Cannot kick member.")
        });
}

function sendRemoveFileRequest(fileid) {
    if (!IS_ROOM_ADMIN) { return }
    if (getSavedUsername() == username) { return }

    let data = {
        room_code: ROOM_CODE,
        fileid: fileid
    };

    data = Object.assign(grabAuthData(), data)

    const options = {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    };

    fetch(API_URL + "rooms/admin/removeFile", options)
        .then(response => response.json())
        .then(result => {
            console.log('Received response from REMOVEFILE request');
            switch (result.status) {
                case true:
                    showSuccess("File removed.")
                    break

                case false:
                    handleApiError(result)
                    break
            }
        })
        .catch(error => {
            console.error('Error while sending REMOVEFILE request', error);
            showError("Cannot remove file.")
        });
}

function sendLockStateRequest(state) {
    if (!IS_ROOM_ADMIN) { return }
    if (getSavedUsername() == username) { return }

    let data = {
        room_code: ROOM_CODE,
        state: state
    };

    data = Object.assign(grabAuthData(), data)

    const options = {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    };

    fetch(API_URL + "rooms/admin/setRoomLockState", options)
        .then(response => response.json())
        .then(result => {
            console.log('Received response from LOCKSTATE request');
            switch (result.status) {
                case true:
                    showSuccess("Room lock state updated.")
                    break

                case false:
                    handleApiError(result)
                    break
            }
        })
        .catch(error => {
            console.error('Error while sending LOCKSTATE request', error);
            showError("Cannot remove file.")
        });
}


