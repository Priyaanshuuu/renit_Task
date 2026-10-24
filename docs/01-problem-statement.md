# Problem statement

## What the client needs

A UK energy utility buys electricity one day before it is delivered. Wind generation depends on the weather, so the buying team must use forecasts when planning purchases.

The app should answer two questions:

1. What wind forecast was available when the buying decision was made?
2. How close was that forecast to the actual wind generation?

## Data allowed

Use only these Elexon datasets at national level:

- [FUELHH actual generation](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream): keep records where `fuelType` is `WIND`. Use `startTime` and `generation`.
- [WINDFOR forecasts](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/WINDFOR/stream): use `startTime`, `publishTime`, and `generation`.

`startTime` is the delivery period. `publishTime` tells us when a forecast was created. Several forecasts can exist for the same delivery period.

## Scope and assumptions

- Cover purchase decisions made in January 2026.
- Interpret this as decision dates 1–31 January and next-day delivery dates 2 January–1 February. Document this assumption.
- Let the user choose a decision cutoff. A 09:00 Europe/London default is an illustrative assumption, not a confirmed market deadline.
- Display the Elexon data's Great Britain coverage accurately.
- This is a forecast analysis dashboard, not a chatbot or a new forecasting model.
- Without customer demand and contract data, it cannot calculate the client's exact purchase requirement.

## Required delivery

- React frontend, Python backend, and Docker.
- Sample app deployed on Vercel or Heroku.
- Public GitHub repository with an anonymous name.
- README explaining files, startup steps, deployed URL, and AI assistance used.
- Unlisted YouTube demo: up to 5 minutes for the client and up to 5 minutes for the technical reviewer; 10 minutes total maximum.
- Submit the links through the supplied form and check access in incognito mode.
- Spend no more than 16 hours. The provided brief does not specify a submission deadline or provide the actual submission-form URL.
