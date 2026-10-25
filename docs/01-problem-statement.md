# Problem statement

I built this pilot for a day-ahead electricity buying workflow. The client is a UK energy utility that needs to review wind forecasts when planning purchases for the following day.

The portal answers two questions:

1. What wind forecast had been published when the buying decision was made?
2. How close was that forecast to actual generation for the delivery day?

## Data scope

I use only the two Elexon datasets allowed by the brief:

- [FUELHH actual generation](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream): records with `fuelType = WIND`, using `startTime` and `generation`.
- [WINDFOR forecasts](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/WINDFOR/stream): forecast revisions using `startTime`, `publishTime`, and `generation`.

`startTime` identifies delivery, while `publishTime` identifies a publication. I preserve multiple publications for the same delivery period so the analysis can reconstruct different decision cutoffs.

## Scope and assumptions

- I interpret January 2026 buying decisions as decision dates 1-31 January, with next-day delivery on 2 January-1 February.
- I use a configurable cutoff with a 09:00 Europe/London default. This is an illustrative assumption; the client's actual deadline still needs confirmation.
- I label the data as Great Britain national operationally metered wind.
- I evaluate published forecasts rather than train a new prediction model.
- Customer demand and contract data would be needed to calculate the client's exact purchase requirement.

## Deliverables from the brief

The brief asks for a React frontend, Python backend, Docker deliverable, a sample app on Vercel or Heroku, and a public GitHub repository with an anonymous name. The README must explain startup, files, deployed links, and AI assistance.

The unlisted YouTube video must contain a customer overview of at most 5 minutes and a technical-review overview of at most 5 minutes, with a 10-minute total limit. The repository, deployment, and video links must be accessible in incognito mode and submitted through the supplied form.

I used the 16-hour limit to keep the pilot focused. The supplied brief does not state a submission deadline or include the submission-form URL. My current progress and remaining deliverables are recorded in [the project steps](steps.md).
