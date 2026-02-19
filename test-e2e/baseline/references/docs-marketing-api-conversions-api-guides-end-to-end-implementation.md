# End-to-end Implementation - Conversions API - Documentation - Meta for Developers

> Source: https://developers.facebook.com/docs/marketing-api/conversions-api/guides/end-to-end-implementation/?translation

---

End-to-end Implementation - Conversions API - Documentation - Meta for Developers

Conversions API

Get Started

Using the API

Verifying Setup

Parameters

Parameter Builder Library

Conversions API for App Events

Conversions API for Offline Events

Conversions API for Business Messaging

Conversion Leads Integration

Dataset Quality API

Handling Duplicate Events

Guides

Payload Helper

Best Practices

Troubleshooting

Conversions API End-to-End Implementation

The Conversions API supports advertisers’ efforts to provide consumers with appropriate data transparency and control while also helping them to continue providing personal experiences. With the API, you can share data directly from your server, rather than through a browser.

Benefits of Integration

Deeper-Funnel Visibility
: The Conversions API allows you to share a wider array of data when compared to the Meta Pixel. With the API, you can make decisions taking into account more information, such as CRM data, lower funnel events (including qualified leads), and multi-site conversion paths across a website and a physical location.

Data Control
:  When used via a Server-Only implementation (for example, without the Meta Pixel), the Conversions API gives you added control over what data you share. You can choose to append insights to your events, providing data such as product margins or historical information, like customer value scores.

Signal Reliability and Resiliency
: Data sharing through the Conversions API may be more reliable than browser-based methods alone, like the Meta Pixel. The API is designed to be less susceptible to issues like a browser crash or connectivity problems. New industry data transmission restrictions may limit the efficacy of cookies and Pixel tracking, so the Conversions API helps you have control on sharing signals that may no longer be captured by the Pixel.

Additional Resources
: View the 
Conversions API Direct Integration Playbook for Developers (PDF) 
 and 
Direct Integration Webinar for Developers

Overview

You can think about your Conversions API integration in two main stages:

Preparation

 — Select which 
type of integration
 makes sense for you, 
define which events to send
, and 
review available optimization options
.

Execution

 — Learn how to 
implement the API
. For this stage, you can also use a 
partner integration
.

The following is a snapshot of the complete integration process:

Requirements

Full Integration

Optimization

Select events to share with Meta with user consent (if any).

Set up your business’ assets: Meta Pixel, Meta Application, Business Manager, Server Connection, System User.

Step 1: One event
 - Sending any event, manually or automated using the system user&#039;s token. Completing this step means you have correctly set up authentication.

Step 2: Fully Integrated
 - You need to be sending some automated events to be considered integrated. Completing this milestone means you are able to optimize for Conversions API even in the event that you stop using the Pixel or the Pixel is blocked.

Once you are fully integrated, send enough automated funnel events to be considered fully onboarded. Then, optimize your match rate based on guidance from Event Match Quality.

Make sure:

The events can be sent via either channel (browser or server) and it is not being double-counted. 

The events are being sent as close to real-time as possible. 

Provide customer information parameters to be used for identity matching.

Existing Pixel Users

If you have an existing Meta Pixel integration, the Conversion API integration should be built as an extension of the Pixel integration, instead of as an entirely different connection.

General Consent

If you have logic for controlling consent with respect to sharing Pixel data, use the same logic with respect to sharing data via Conversions API.

Alternatives

If you want to optimize your ads for app events, please use the 
App Events API
.

Preparation

Pick Your Integration Type

To start, select the integration option you would like to implement:

Setup

Approach Description

Redundant Setup (Recommended)

Send all events via both Pixel and Conversions API. This is the recommended setup for those who would like to keep the Pixel on their website, and are able to fully adopt the Conversions API.

To succeed, you must be able to generate a persistent 
event_id
 for both Pixel and Conversions API events. This means sending the same 
event_name
 and 
event_id
 on both the Pixel and the Conversions API event, in order to 
deduplicate identical events
.

This setup provides performance on par or better than using only the browser Pixel. The server can capture events that may not be tracked by the browser, such as purchases that occur on a separate website, lead conversions, or phone calls.

Split Setup

Send different types of events via Pixel and Conversions API. For example, you could send 
PageView
 and 
ViewContent
 via Pixel, and  
Lead
 or 
Purchase
 via Conversions API.

While this option is not as optimal as a redundant setup, you may consider it if you do not want to use a fully redundant setup. Take into consideration that you may need to complete additional work as browser changes are implemented.

Server-Only Implementation

Only send events through the Conversions API, instead of through the browser. We recommend implementing either a 
redundant setup
 or a 
split setup
 before switching to this approach.

Define Events to Send

Once you have chosen your integration approach, you can define which events you want to send. Signals are most useful if they are matched to Meta user IDs, so it is important to think through what parameters you are sending us with an event and how often you would like to send them.

Event Options

Send events that are most relevant to your business. See a full list of supported 
standard
 and 
custom
 Meta events.

Event Parameters

You can send multiple parameters inside each event. See 
parameters used by Conversions API
 to learn more about those fields.

You can add multiple types of IDs to your events, including 
event_id
, 
external_id
 and 
order_id
. It’s important to know the difference between these parameters:

ID

Description

How It Is Used

External ID

Your unique ID for a specific customer.

Learn more about 
External ID
.

Event ID

A unique ID for a given event.

Used on event deduplication. This field is very important if you are sending events via both browser Pixel and conversions API.

Order ID

A unique ID for a given order. This parameter only works for purchase events and expects an 
order_id
 field in 
custom_data
.

This implementation is limited to select Meta partners. Contact your Meta representative for access.

Used on purchase event deduplication, if you send events via both browser Pixel and conversions API.

Once you sent us your first order, we discard the second one if:

You send a second event with the same 
order_id
 within a specific time window, and
We resolve that the same user completed both orders.

You can deduplicate purchase events within two windows: 48 hours (recommended) or 28 days. This is the window between the first and second instances of the same event.

Data Freshness

We recommend that you send events in real time or in 
batches
 based on a specific timeline via the Conversions API. Sending your events in real time or within 1 hour helps ensure that they can be used for attribution and optimized for ad delivery.

Sending your events more than 2 hours after they occurred can cause a significant decrease in performance for ads optimized for those events. Events sent with a delay of 24 hours or more may experience significant issues with attribution and optimized ad delivery.

If you’re sending events with long conversion windows, send the event as close to real time as possible from the point at which the full conversion is completed.

Move on to the next step once you have:

A list of events to send.

The specific fields you want to send with each event.

Defined how frequently you will send events.

Available Optimization Types

The Conversions API offers the following optimization types:

Optimization Option

Description

Conversions Optimization

Optimize ad delivery to show ads to people most likely to make a conversion.

Value Optimization (also known as Return on Ads Spend Optimization)

Optimize ad delivery to show ads to people most likely to make a conversion of a specified value, such as purchases over $50.

Dynamic Product Ads

Optimize ad delivery to show ads for specific products to people most likely to purchase those specific products.

Execution

There are two ways to implement your integration:

Direct Integration
 — You, as an advertiser, directly implement conversions API.

Integration as a Platform
 — You, as a marketing partner, offer conversions API as a service to your clients.

Advertisers using conversions API through one of our marketing partners should follow our partner’s implementation guidelines.

Direct Integration

Step 1: Set Up Requirements

Prior to using the Conversions API, set up the following assets:

Asset

Description

Meta Pixel

When you send events through the Conversions API, they’re processed and stored in the same way as the events you send through your Pixel. When you implement the Conversions API, you select which Pixel you want to send your events to.

Sending your Conversions API events to a Pixel lets you use your Conversions API events in the same way you use your browser-based Pixel events for measurement, attribution, and ad delivery optimization.  We recommend sending events from the browser and your server to the same Meta Pixel ID.

Business Manager

You need a Business Manager to use the API. Business Manager helps advertisers integrate Meta marketing efforts across their business and with external partners. If you don&#039;t have a Business Manager, see the Help Center article on how to 
Create a Business Manager
.

Access Token

To use the Conversions API, you need an 
access token
. There are two ways of getting your access token:

Via Events Manager
 (Recommended)

Using Your Own App

Move on to 
Implement the API
 once you have the assets ready. Remember to save IDs for your assets, since you use those on your API calls.

Step 2: Implement the API

Once you are done with the requirements, start the implementation process. While building on the Conversions API, always check the 
developer documentation
.

Test Calls (Optional)

If this is your first time using the API, start with a test call. To do that, you need a payload and a method for making API calls. After the call is completed, check Events Manager to verify the call worked as expected.

Payload

API Call Method

Use the 
Payload Helper
 to generate a sample payload to be sent with your call. Follow the instructions listed on the tool. Your payload should look something like this:

&#123;
  &quot;data&quot;: [
   &#123;
    &quot;event_name&quot;: &quot;Purchase&quot;,
    &quot;event_time&quot;: 1601673450,
    &quot;user_data&quot;: &#123;
      &quot;em&quot;: &quot;7b17fb0bd173f625b58636fb796407c22b3d16fc78302d79f0fd30c2fc2fc068&quot;,
      &quot;ph&quot;: null
     &#125;,
    &quot;custom_data&quot;: &#123;
      &quot;currency&quot;: &quot;USD&quot;,
      &quot;value&quot;: &quot;142.52&quot;
    &#125;
   &#125;
  ]
&#125;

If you want to test your payload from the Payload Helper, add your Pixel ID under 
Test this Payload
 and click on 
Send to Test Events
. You should be able to see the event on 
Events Manager
 &gt; 
Your Pixel
 &gt; 
Test Events
. Learn more about the 
Test Events Tool
.

Once you are satisfied with your payload, decide how you want to make your call. You can use our Graph API Explorer (see 
Guide
) or your own servers. If you are using your servers, you can use CURL or the Meta Business SDK—We highly recommend 
using the Meta Business SDK
.

Independently on your call method, you should call the 
/&#123;pixel_id&#125;/events
 endpoint and attach the JSON data generated by the Payload Helper. Once you make the call, you should get a response like this:

&#123;
  &quot;events_received&quot;: 1,
  &quot;messages&quot;: [],
  &quot;fbtrace_id&quot;: &lt;FB-TRACE-ID&gt;
&#125;

After you complete your first call, verify your events on 
Events Manager
 &gt; 
Your Pixel
 &gt; 
Overview
.

Move on to 
Send and Verify Events
 once you have checked your test events in Events Manager.

Send and Verify Events

To start sending events, make a 
POST
 request to the API’s 
/events
 edge. Attach a payload to your call —if you need help generating your payload, visit the 
Payload Helper
. See the following resources for more information and code samples:

Using the API &gt; Send requests

Dropped Events

Upload Time versus Event Transaction Time

Batch Requests

Hashing

After you start sending events, go to Events Manager and confirm that we have received the events you sent. Learn how to 
Verify Your Events
.

If your implementation is complementary to a browser Pixel, move on to 
deduplication settings
. Otherwise, you are all set! Check 
Support
 if you still have questions.

Step 3: Add Parameters for Deduplication

If you’re sending identical events from your Pixel and through the Conversions API, you need to set up deduplication for your events sent via both channels. First, read 
developer documentation to understand the deduplication logic
.

Event-based deduplication

If we find the same server key combination (
event_id
, 
event_name
) and browser key combination (
eventID
, 
event
) sent to the same Pixel ID within 48 hours, we discard the later sent duplicate events.

To help ensure your events are deduplicated:

For the corresponding events, make sure the following parameters are set to the same value:

event_id
 from your server event and 
eventID
 from your browser event

event_name
 from your server and browser events

After you send duplicate events, check Events Manager to see if the correct events are being dropped.

Ensure that each unique event sent via both Pixel and Conversions API has its own 
event_id
. This ID should not be shared with other events.

Alternative to event-based deduplication

While Event ID will always be the best way to deduplicate events, it&#039;s a fairly complex implementation. You can leverage alternative solutions by using external_id or fbp parameters. If you have configured the external_id or fbp parameters to be passed via both browser and server, we will deduplicate events automatically if we see the same event with same external_id or fbp parameters within 48 hours.

Optional Step 4: Explore 
Business SDK Features

The Meta Business SDK has advanced features designed especially for Conversions API users:

Asynchronous Requests
 — Use this feature if you do not want to block your program’s execution to wait for a request to be completed. With this approach, you make your request and get a signal back from the server once it has been completed. While you wait for the response, the program can keep executing.

Concurrent Batching
 — Leverage asynchronous requests to increase throughput by utilizing resources more efficiently. Create batched requests to support use cases like event request workers, cron jobs, and more. 

HTTP Service Interface
 — Override the Business SDK’s default HTTP service and implement your own custom service with your preferred method or library.

Integration as a Platform

The following instructions are for partners offering conversions API as a service to advertisers.

Step 1: Set Up Requirements

Your app should get the following features and permissions:

Access Level: 
Advanced Access

Feature: 
Ads Management Standard Access

Permissions: 

ads_management

 or 

business_management

 and 

pages_read_engagement

 and 

ads_read

. 

Step 2: Send Events on Behalf of Clients

1. Facebook Login for Business (Recommended for partners)

Facebook Login for Business
 is the preferred authentication and authorization solution for Tech Providers and business app developers who need access to their business clients&#039; assets. It allows you to specify the access token type, types of assets, and permissions your app needs, and save it as a set (configuration). You can then present the set to your business clients who can complete the flow and grant your app access to their business assets.

2. Meta Business Extension

Meta Business Extension
 returns all the necessary information needed to send events on behalf of the client via the following process. Meta Business Extension provides an endpoint to retrieve system user access tokens created in the client’s Business Manager. This process includes permissions to send server events and is done automatically and in a secured way.

The endpoint requires the user access token as input parameter. For new Meta Business Extension users, call this endpoint the endpoint to fetch the system user access token after you finish setting up Meta Business Extension. Existing users need to ask for re-authentication before calling the new API endpoint.

Facebook Business Extension is currently only available to approved partners. If you are interested in becoming a partner, contact your Meta representative for access.

3. Business On behalf Of: Client shares dataset to the partner’s Business Manager

The client shares their dataset to the partner via Business Manager settings, see ‘Client system user’s access token’ section  or via 
API through the On Behalf Of onboarding method
. You can assign the partner system user to the client pixel and generate an access token to send server events by manually creating a System User Access Token. This can be done via the Conversions API inside the pixel settings above. On the API side, you need to request access to the 
client’s ad account
 managing the dataset and 
proceed sharing pixels via API
.

4. Client system user’s access token

This is the similar onboarding flow for direct integration. You will have your client 
manually create a System User Access Token
 via the Conversions API inside the dataset settings. Then, you can send events to the advertiser’s dataset with that token. A system user or an admin system user must install the app that will be used to generate the access token. With this setup, your app is allowed to call APIs on behalf of this system user or admin system user.

Note
: If the partner system leverages this method, their token will be limited to sending data only to Meta. The token can’t be used to run API GET data requests.

Step 3: Attribute Events to Your Platform

To attribute conversions API events to your platform, use the 
partner_agent
 field. This allows you to set your own platform identifier when sending events on behalf of a client. If you are a managed partner, work with your Meta Representative to agree on an identifier for your platform. This value should be in a format that is less than 23 characters and includes at least two alphabetical characters. Then, send it with each server event.

Always provide an up-to-date setup guide for advertisers looking to activate the integration on your platform.

Support

For All Partners

See information about debugging and Business Help Center articles
.

For Managed Partners

Provide the following information to your Meta Representative, so they can help with testing integrations and troubleshooting: Business Manager ID, App ID, Pixel IDs.

API Documentation

Get started
 - Test the API from your own Business Manager

Using the API

Best Practices - Conversions API

Set Up Conversions API as a Platform

Standard Meta Events

Custom Meta Events

Parameters

Payload Helper

Data Processing Options for Conversions API and Offline Conversions API

If you want to optimize for app events, use App Event API

 -->

                                                                                                                                                                                                                                                                                                                                                                                                            

                                                                                                                                                                                                                                                                                                                                                                                                   

 -->