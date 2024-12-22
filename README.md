
# Throne and Liberty Guild DKP Management Bot

![Bot Logo](https://cdn.discordapp.com/avatars/1319475647692673084/190ff4d1fea02d7b2d128be846dbe025?size=256)

## Table of Contents

- [Introduction](#introduction)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
  - [User Commands](#user-commands)
  - [Administrator Commands](#administrator-commands)
- [Security Considerations](#security-considerations)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgements](#acknowledgements)

## Introduction

Welcome to the **Throne and Liberty Guild DKP Management Bot**! This Discord bot is designed to help guild leaders and members manage Dragon Kill Points (DKP) efficiently. Whether you're tracking attendance, managing absences, or awarding points for event participation, this bot streamlines the process, ensuring fair and transparent DKP distribution within your guild.

## Features

- **DKP Tracking:** Automatically track and display DKP points for each guild member.
- **Absence Management:** Justify absences by days or specific events to prevent unfair point deductions.
- **Event Management:** Create events, assign points, and handle attendance seamlessly.
- **Late Arrival Justifications:** Allow members to justify late arrivals to events, reversing any penalties.
- **Role-Based Permissions:** Ensure only authorized personnel can execute administrative commands.
- **Data Persistence:** All data is stored securely in JSON files, ensuring persistence across bot restarts.
- **Automated Clean-Up:** Regularly cleans expired absences and outdated event data.
- **Logging:** Maintains logs of all critical actions for auditing and monitoring purposes.

## Prerequisites

Before setting up the bot, ensure you have the following:

- **Python 3.8+** installed on your system. You can download it from [here](https://www.python.org/downloads/).
- A **Discord account** and a **Discord server** where you have permissions to add bots.
- **Git** installed on your system to clone the repository. Download it [here](https://git-scm.com/downloads).
- Basic knowledge of Discord bot permissions and roles.

## Installation

1. **Clone the Repository:**

   ```bash
   git clone https://github.com/yourusername/throne-and-liberty-dkp-bot.git
   cd throne-and-liberty-dkp-bot
   ```

2. **Create a Virtual Environment (Optional but Recommended):**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

## Configuration

1. **Create a Discord Bot:**

   - Go to the [Discord Developer Portal](https://discord.com/developers/applications).
   - Click on **"New Application"**, name it, and create the application.
   - Navigate to the **"Bot"** tab, click **"Add Bot"**, and confirm.
   - Copy the **Bot Token**; you'll need it for configuration.

2. **Set Up Environment Variables:**

   - Create a `.env` file in the root directory of the project.

     ```bash
     touch .env
     ```

   - Open the `.env` file and add the following, replacing placeholder values with your actual data:

     ```env
     DISCORD_BOT_TOKEN=your_bot_token_here
     CANAL_ADMIN=admin_channel_id
     CANAL_AUSENCIAS=absence_channel_id
     CANAL_TARDE=late_arrivals_channel_id
     CANAL_CONSULTA=consultation_channel_id
     ADMINS_IDS=admin_id1,admin_id2,admin_id3  # Comma-separated Discord user IDs with admin privileges
     ```

     - **DISCORD_BOT_TOKEN:** The token you copied from the Discord Developer Portal.
     - **CANAL_ADMIN:** The ID of the channel designated for administrative commands.
     - **CANAL_AUSENCIAS:** The ID of the channel where absence-related commands are handled.
     - **CANAL_TARDE:** The ID of the channel designated for handling late arrivals.
     - **CANAL_CONSULTA:** The ID of the channel used for DKP consultations.
     - **ADMINS_IDS:** Comma-separated Discord user IDs that have administrative privileges.

3. **Invite the Bot to Your Server:**

   - In the Discord Developer Portal, navigate to the **"OAuth2"** tab.
   - Under **"Scopes"**, select **"bot"**.
   - Under **"Bot Permissions"**, select the necessary permissions (e.g., Send Messages, Manage Messages).
   - Copy the generated OAuth2 URL and open it in your browser to invite the bot to your server.

## Usage

Once the bot is running and added to your Discord server, you can use the following commands.

### User Commands

#### `!ausencia`

Justify an absence either by specifying the number of days or a specific event.

- **Usage for Regular Users:**
  - **By Days:** `!ausencia <days>`
    - **Example:** `!ausencia 2`
    - **Effect:** Justifies absence for the next 2 days.
  - **By Event:** `!ausencia <event_name>`
    - **Example:** `!ausencia RaidFinal`
    - **Effect:** Justifies absence for the specified event.

### Administrator Commands

#### `!evento`

Create an event and manage DKP points based on attendance.

- **Usage:**
  ```bash
  !evento <event_name> <points> [NORESTA] [user1] [user2] ...
  ```
- **Parameters:**
  - `<event_name>`: Name of the event.
  - `<points>`: Points to be awarded.
  - `NORESTA` (optional): If included, no points are deducted from non-mentioned users.
  - `[user1] [user2] ...`: List of users who attended the event.

- **Example:**
  ```bash
  !evento PVP 10 juan
  ```
  - **Effect:**
    - **Juan** receives **+10 DKP**.
    - **Other users** lose **-20 DKP** each unless `NORESTA` is specified.

#### `!vincular`

Link a Discord member to their guild name.

- **Usage:**
  ```bash
  !vincular @member GuildName
  ```
- **Example:**
  ```bash
  !vincular @martin Martin
  ```
  - **Effect:** Links the Discord member **@martin** to the guild name **Martin**.

#### `!borrarusuario`

Remove a user from the DKP system.

- **Usage:**
  ```bash
  !borrarusuario <GuildName>
  ```
- **Example:**
  ```bash
  !borrarusuario Juan
  ```
  - **Effect:** Removes **Juan** from the DKP tracking system.

#### `!sumardkp`

Add DKP points to a user.

- **Usage:**
  ```bash
  !sumardkp <GuildName> <points>
  ```
- **Example:**
  ```bash
  !sumardkp Juan 15
  ```
  - **Effect:** Adds **15 DKP** to **Juan**.

#### `!restardkp`

Subtract DKP points from a user.

- **Usage:**
  ```bash
  !restardkp <GuildName> <points>
  ```
- **Example:**
  ```bash
  !restardkp Martin 5
  ```
  - **Effect:** Subtracts **5 DKP** from **Martin**.

#### `!ausencia_vacaciones`

Mark a user as being on vacation.

- **Usage:**
  ```bash
  !ausencia_vacaciones <GuildName>
  ```
- **Example:**
  ```bash
  !ausencia_vacaciones Juan
  ```
  - **Effect:** Marks **Juan** as on vacation, preventing point adjustments during this period.

#### `!ausencia_volvio`

Mark a user as returned from vacation.

- **Usage:**
  ```bash
  !ausencia_volvio <GuildName>
  ```
- **Example:**
  ```bash
  !ausencia_volvio Juan
  ```
  - **Effect:** Marks **Juan** as active again and removes any active absences.

### `!llegue_tarde`

Justify a late arrival to an event.

- **Usage:**
  ```bash
  !llegue_tarde <event_name>
  ```
- **Example:**
  ```bash
  !llegue_tarde PVP
  ```
  - **Effect:** If **Martin** was penalized for missing the **PVP** event, this command will revert the penalty and add the event points as if he attended.

### `!dkp`

Check DKP points for a user or view the entire DKP leaderboard.

- **Usage:**
  - **Check Specific User:**
    ```bash
    !dkp <GuildName>
    ```
    - **Example:** `!dkp Juan`
  - **View Leaderboard:**
    ```bash
    !dkp
    ```
    - **Effect:** Displays a sorted list of all users and their DKP points.

## Security Considerations

To ensure the integrity and security of your DKP system, consider implementing the following measures:

1. **Role-Based Access Control:**
   - Ensure that only designated roles (e.g., Admins, Officers) can execute administrative commands.
   - Regular users should only have access to non-critical commands.

2. **Input Validation:**
   - Validate all user inputs to prevent injection attacks or malformed data.
   - Restrict event and user names to alphanumeric characters and underscores.

3. **Rate Limiting:**
   - Implement cooldowns on sensitive commands to prevent spamming or abuse.
   - Example: Limit `!llegue_tarde` to once per event per user.

4. **Logging and Monitoring:**
   - Maintain logs of all critical actions, such as point additions/removals and user linkages.
   - Regularly review logs to detect and address suspicious activities.

5. **Secure Data Storage:**
   - Ensure that JSON files (`scores.json`, `events.json`) are stored securely with appropriate file permissions.
   - Regularly back up data to prevent loss.

6. **Error Handling:**
   - Gracefully handle errors and provide meaningful feedback to users without exposing sensitive information.
   - Implement try-except blocks where necessary to prevent crashes.

7. **Regular Updates:**
   - Keep all dependencies updated to benefit from security patches and improvements.
   - Review and update the bot's codebase periodically to address potential vulnerabilities.

## Contributing

Contributions are welcome! If you'd like to improve the bot, follow these steps:

1. **Fork the Repository:**

   Click the **Fork** button at the top right of the repository page.

2. **Clone Your Fork:**

   ```bash
   git clone https://github.com/yourusername/throne-and-liberty-dkp-bot.git
   cd throne-and-liberty-dkp-bot
   ```

3. **Create a New Branch:**

   ```bash
   git checkout -b feature/YourFeatureName
   ```

4. **Make Your Changes:**

   Implement your feature or bug fix.

5. **Commit Your Changes:**

   ```bash
   git commit -m "Add feature: YourFeatureName"
   ```

6. **Push to Your Fork:**

   ```bash
   git push origin feature/YourFeatureName
   ```

7. **Create a Pull Request:**

   Go to the original repository and create a pull request from your fork's branch.

## License

This project is licensed under the [MIT License](LICENSE). You are free to use, modify, and distribute it as per the license terms.

## Acknowledgements

- [discord.py](https://discordpy.readthedocs.io/en/stable/) - The Python library used to interact with the Discord API.
- [Python](https://www.python.org/) - The programming language used for this bot.
- [Dotenv](https://pypi.org/project/python-dotenv/) - Used for managing environment variables.

---
