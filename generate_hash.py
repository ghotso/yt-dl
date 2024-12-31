import bcrypt
import json
import getpass

def add_user(username, password):
    """Add or update a user with the given username and password."""
    try:
        with open('users.json', 'r') as f:
            users_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        users_data = {"users": []}

    # Generate a new salt and hash the password
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(12))
    hash_str = hashed.decode('utf-8')

    # Check if user exists and update, or add new user
    user_exists = False
    for user in users_data["users"]:
        if user["username"] == username:
            user["password_hash"] = hash_str
            user_exists = True
            break

    if not user_exists:
        users_data["users"].append({
            "username": username,
            "password_hash": hash_str
        })

    # Write updated data back to file
    with open('users.json', 'w') as f:
        json.dump(users_data, f, indent=4)
    print(f"User '{username}' has been {'updated' if user_exists else 'added'} successfully.")

def main():
    """Interactive user management."""
    print("FLAC Downloader User Management")
    print("------------------------------")
    
    while True:
        print("\nOptions:")
        print("1. Add/Update user")
        print("2. Add default admin user")
        print("3. Exit")
        
        choice = input("\nEnter your choice (1-3): ").strip()
        
        if choice == "1":
            username = input("Enter username: ").strip()
            password = getpass.getpass("Enter password: ")
            confirm = getpass.getpass("Confirm password: ")
            
            if password != confirm:
                print("Passwords do not match!")
                continue
                
            add_user(username, password)
            
        elif choice == "2":
            add_user("admin", "admin")
            print("Added default admin user (username: admin, password: admin)")
            
        elif choice == "3":
            break
            
        else:
            print("Invalid choice!")

if __name__ == "__main__":
    main() 