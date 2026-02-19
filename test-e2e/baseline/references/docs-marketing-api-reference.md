# API Reference - Marketing API - Documentation - Meta for Developers

> Source: https://developers.facebook.com/docs/marketing-api/reference/

---

API Reference - Marketing API - Documentation - Meta for Developers

Marketing API

Overview

Get Started

Ad Creative

Bidding

Ad Rules Engine

Audiences

Insights API

Brand Safety and Suitability

Best Practices

Troubleshooting

API Reference

Changelog

Marketing API Version

v24.0

Marketing API Reference

Marketing API Root Nodes

This is a full list of root nodes for the Facebook Marketing API with links to reference docs for each. For background on the API&#039;s architecture how to call root nodes and their edges, see 
Using the Graph API
.

To access all reference information you will need to be logged in to Facebook.

Node

Description

/&#123;AD_ACCOUNT_USER_ID&#125;

Someone on Facebook who creates ads. Each ad user can have a role on several ad accounts.

/act_&#123;AD_ACCOUNT_ID&#125;

Represents the business entity managing ads.

/&#123;AD_ID&#125;

Contains information for an ad, such as creative elements and measurement information.

/&#123;AD_CREATIVE_ID&#125;

Format for your image, carousel, collection, or video ad.

/&#123;AD_SET_ID&#125;

Contains all ads that share the same budget, schedule, bid, and targeting.

/&#123;AD_CAMPAIGN_ID&#125;

Defines your ad campaigns&#039; objective. Contains one or more ad set.

User

Edges

Edge

Description

/adaccounts

All ad accounts associated with this person

/accounts

All pages and places that someone is an admin of

/promotable_events

All promotable events you created or promotable page events that belong to pages you are an admin for

Ad Account

All collections of ad objects in Marketing APIs belong to an 
ad account
.

Edges

The most popular edges of the Ad Account node. Visit the 
Ad Account Edges reference
 for a complete list of all edges.

Edge

Description

/adcreatives

Defines your ad&#039;s appearance and content

/adimages

Library of images to use in ad creatives. Can be uploaded and managed independently

/ads

Data for an ad, such as creative elements and measurement information

/adsets

Contain all ads that share the same budget, schedule, bid, and targeting

/advideos

Library of videos for use in ad creatives. Can be uploaded and managed independently

/campaigns

Define your campaigns&#039; objective and contain one or more ad sets

/customaudiences

The custom audiences owned by/shared with this ad account

/insights

Interface for insights. De-dupes results across child objects, provides sorting, and async reports.

/users

List of people assocated with an ad account

Ad

An individual ad associated with an ad set.

Edges

The most popular edges of the Ad node. Visit the 
Ad Edges reference
 for a complete list of all edges.

Edge

Description

/adcreatives

Defines your ad&#039;s appearance and content

/insights

Insights on your advertising performance.

/leads

Any leads associated with with a Lead Ad.

/previews

Generate ad previews from an existing ad

Ad Set

An ad set is a group of ads that share the same daily or lifetime budget, schedule, bid type, bid info, and targeting data.

Edges

The most popular edges of the Ad Set node. Visit the 
Ad Set Edges reference
 for a complete list of all edges.

Edge

Description

/activities

Log of actions taken on the ad set

/adcreatives

Defines your ad&#039;s content and appearance

/ads

Data necessary for an ad, such as creative elements and measurement information

/insights

Insights on your advertising performance.

Ad Campaign

A campaign is the highest level organizational structure within an ad account and should represent a single objective for an advertiser.

Edges

The most popular edges of the Ad Campaign node. Visit the 
Ad Campaign Edges reference
 for a complete list of all edges.

Edge

Description

/ads

Data necessary for an ad, such as creative elements and measurement information

/adsets

Contain all ads that share the same budget, schedule, bid, and targeting.

/insights

Insights on your advertising performance.

Ad Creative

The format which provides layout and contains content for the ad.

Edges

The most popular edges of the Ad Creative node. Visit the 
Ad Creative Edges reference
 for a complete list of all edges.

Edge

Description

/previews

Generate ad previews from the existing ad creative object

 -->

                                                                                                                                                                                                                                                                                                                                                                                                            

                                                                                                                                                                                                                                                                                                                                                                                                   

 -->