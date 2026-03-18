library(shiny)
library(googlesheets4)

# --- Global setup ---
PROBLEMS_FILE <- "adjudication_export.csv"

# Google Sheets auth via service account key
gs4_auth(path = "service-account-key.json")

# Google Sheet ID — set this after creating the sheet
SHEET_ID <- Sys.getenv("SURVEY_SHEET_ID", "1db_LGDpCv_QJ4UEOpODvh0qN3jTddZYu-IcfDDzktfo")

problems_df <- read.csv(PROBLEMS_FILE, stringsAsFactors = FALSE)
TOTAL_PROBLEMS <- nrow(problems_df)

RATERS <- c("Tom", "Caroline", "Becky", "Alice", "Patrick")

RATING_SCALE <- c(
  "1" = "Not a problem at all",
  "2" = "Minor problem",
  "3" = "Moderate problem",
  "4" = "Severe problem",
  "5" = "Very severe problem"
)

load_ratings <- function(rater_id) {
  tryCatch({
    df <- read_sheet(SHEET_ID, sheet = rater_id)
    if (nrow(df) > 0 && "rating" %in% names(df) && "row_index" %in% names(df)) {
      return(setNames(as.integer(df$rating), as.character(df$row_index)))
    }
  }, error = function(e) {
    # Sheet tab doesn't exist yet — create it
    tryCatch({
      sheet_add(SHEET_ID, sheet = rater_id)
      range_write(SHEET_ID,
        data = data.frame(row_index = integer(0), rating = integer(0)),
        sheet = rater_id
      )
    }, error = function(e2) {
    })
  })
  return(setNames(integer(0), character(0)))
}

save_ratings <- function(rater_id, ratings) {
  if (length(ratings) > 0) {
    df <- data.frame(
      row_index = as.integer(names(ratings)),
      rating = as.integer(ratings),
      stringsAsFactors = FALSE
    )
    tryCatch({
      range_clear(SHEET_ID, sheet = rater_id)
      range_write(SHEET_ID, data = df, sheet = rater_id)
    }, error = function(e) {
      # If sheet doesn't exist, create and write
      tryCatch({
        sheet_add(SHEET_ID, sheet = rater_id)
        range_write(SHEET_ID, data = df, sheet = rater_id)
      }, error = function(e2) {
        warning(paste("Failed to save ratings for", rater_id, ":", e2$message))
      })
    })
  }
}

# --- UI ---
ui <- fluidPage(
  title = "Survey Problem Rating",
  # Keep-alive: ping server every 60s to prevent websocket timeout
  tags$script(HTML("
    setInterval(function() {
      Shiny.setInputValue('keepalive', Math.random());
    }, 60000);
  ")),
  tags$style(HTML("
    .btn-rated { background-color: #28a745 !important; color: white !important;
                 border-color: #28a745 !important; }
    .rating-btn { margin-bottom: 5px; }
    .question-box { background-color: #d1ecf1; border: 1px solid #bee5eb;
                    border-radius: 5px; padding: 15px; margin-bottom: 15px; }
    .problem-box { background-color: #fff3cd; border: 1px solid #ffeeba;
                   border-radius: 5px; padding: 15px; margin-bottom: 15px; }
    .rating-label { font-size: 0.85em; color: #666; margin-top: 2px; }
  ")),

  sidebarLayout(
    sidebarPanel(
      h3("Rating Dashboard"),
      selectInput("rater_id", "Select your name:",
                  choices = c("Select..." = "", setNames(RATERS, RATERS))),
      textOutput("problem_count"),
      hr(),
      h4("Navigation"),
      numericInput("jump_to", paste0("Jump to problem (1-", TOTAL_PROBLEMS, "):"),
                   value = 1, min = 1, max = TOTAL_PROBLEMS),
      actionButton("go_btn", "Go", class = "btn-sm"),
      checkboxInput("show_unrated", "Show unrated problems only"),
      hr(),
      h4("Progress"),
      textOutput("progress_text"),
      uiOutput("progress_bar"),
      hr(),
      downloadButton("download_csv", "Download CSV"),
      textOutput("download_info"),
      width = 3
    ),

    mainPanel(
      uiOutput("main_content"),
      width = 9
    )
  )
)

# --- Server ---
server <- function(input, output, session) {

  rv <- reactiveValues(
    current_index = 1,
    ratings = list()
  )

  # Load ratings when rater is selected
  observeEvent(input$rater_id, {
    req(input$rater_id != "")
    if (is.null(rv$ratings[[input$rater_id]])) {
      rv$ratings[[input$rater_id]] <- load_ratings(input$rater_id)
    }
    rv$current_index <- 1
    updateNumericInput(session, "jump_to", value = 1)
  })

  # Current rater's ratings
  rater_ratings <- reactive({
    req(input$rater_id != "")
    r <- rv$ratings[[input$rater_id]]
    if (is.null(r)) setNames(integer(0), character(0)) else r
  })

  # Active problem indices (all or unrated only)
  active_indices <- reactive({
    all_idx <- seq_len(TOTAL_PROBLEMS)
    if (input$show_unrated) {
      rated <- names(rater_ratings())
      unrated <- all_idx[!as.character(all_idx) %in% rated]
      return(unrated)
    }
    all_idx
  })

  # Snap to first unrated when filter toggles on
  observeEvent(input$show_unrated, {
    req(input$rater_id != "")
    idx <- active_indices()
    if (length(idx) > 0 && !rv$current_index %in% idx) {
      rv$current_index <- idx[1]
      updateNumericInput(session, "jump_to", value = idx[1])
    }
  }, ignoreInit = TRUE)

  # Number rated
  num_rated <- reactive({
    length(rater_ratings())
  })

  # Sidebar outputs
  output$problem_count <- renderText({
    paste0(TOTAL_PROBLEMS, " problems to rate")
  })

  output$progress_text <- renderText({
    req(input$rater_id != "")
    paste0(num_rated(), " / ", TOTAL_PROBLEMS)
  })

  output$progress_bar <- renderUI({
    req(input$rater_id != "")
    pct <- round(100 * num_rated() / TOTAL_PROBLEMS)
    tags$div(class = "progress",
      tags$div(class = "progress-bar progress-bar-success", role = "progressbar",
               style = paste0("width: ", pct, "%;"),
               paste0(pct, "%"))
    )
  })

  output$download_info <- renderText({
    req(input$rater_id != "")
    n <- num_rated()
    if (n > 0) paste0(n, " rating(s) ready to download") else ""
  })

  # Navigation: Go button
  observeEvent(input$go_btn, {
    req(input$jump_to >= 1, input$jump_to <= TOTAL_PROBLEMS)
    rv$current_index <- input$jump_to
  })

  # Navigation: Previous
  observeEvent(input$prev_btn, {
    idx <- active_indices()
    pos <- which(idx == rv$current_index)
    if (length(pos) > 0 && pos > 1) {
      rv$current_index <- idx[pos - 1]
      updateNumericInput(session, "jump_to", value = idx[pos - 1])
    }
  })

  # Navigation: Next
  observeEvent(input$next_btn, {
    idx <- active_indices()
    pos <- which(idx == rv$current_index)
    if (length(pos) > 0 && pos < length(idx)) {
      rv$current_index <- idx[pos + 1]
      updateNumericInput(session, "jump_to", value = idx[pos + 1])
    }
  })

  # Rating button observers
  lapply(1:5, function(r) {
    observeEvent(input[[paste0("rate_", r)]], {
      req(input$rater_id != "")
      rater <- input$rater_id
      key <- as.character(rv$current_index)

      ratings <- rv$ratings[[rater]]
      if (is.null(ratings)) ratings <- setNames(integer(0), character(0))
      ratings[key] <- r
      rv$ratings[[rater]] <- ratings
      save_ratings(rater, ratings)

      # Auto-advance to next problem
      idx <- active_indices()
      pos <- which(idx == rv$current_index)
      if (length(pos) > 0 && pos < length(idx)) {
        rv$current_index <- idx[pos + 1]
        updateNumericInput(session, "jump_to", value = idx[pos + 1])
      }
    }, ignoreInit = TRUE)
  })

  # Main content
  output$main_content <- renderUI({
    if (input$rater_id == "") {
      return(tags$div(class = "alert alert-warning",
        "Please select your name in the sidebar to begin rating."))
    }

    idx <- active_indices()

    # All done case
    if (length(idx) == 0 && input$show_unrated) {
      return(tags$div(
        tags$div(class = "alert alert-success",
          tags$h4(paste0("All ", TOTAL_PROBLEMS, " problems have been rated!")),
          "Download your ratings using the button in the sidebar."
        )
      ))
    }

    # Current problem
    ci <- rv$current_index
    prob <- problems_df[ci, ]
    existing <- rater_ratings()[as.character(ci)]

    pos <- which(idx == ci)
    is_first <- length(pos) > 0 && pos == 1
    is_last <- length(pos) > 0 && pos == length(idx)

    # Build rating buttons
    rating_buttons <- lapply(1:5, function(r) {
      btn_class <- if (!is.na(existing) && existing == r) {
        "btn btn-success rating-btn"
      } else {
        "btn btn-default rating-btn"
      }
      column(2,
        actionButton(paste0("rate_", r), label = as.character(r),
                     class = btn_class, width = "100%"),
        tags$div(class = "rating-label", RATING_SCALE[as.character(r)])
      )
    })

    tagList(
      h2(paste0("Problem ", ci, " of ", TOTAL_PROBLEMS)),

      # Question display
      tags$div(class = "question-box",
        tags$strong(paste0(prob$question_id, " \u2014 ", prob$question_label)),
        tags$p(prob$question_text),
        tags$p(tags$strong("Response scale: "), prob$response_scale)
      ),

      # Problem display
      tags$div(class = "problem-box",
        tags$strong(prob$theme),
        tags$p(prob$problem_description)
      ),

      # Rating
      tags$h4("How would you rate the severity of this problem in terms of the respondent's ability to provide an accurate answer?"),
      fluidRow(rating_buttons),

      # Current rating display
      if (!is.na(existing)) {
        tags$div(class = "alert alert-success", style = "margin-top: 15px;",
          paste0("Current rating: ", existing, " - ", RATING_SCALE[as.character(existing)]))
      },

      # Navigation buttons
      tags$div(style = "margin-top: 20px;",
        fluidRow(
          column(4, {
            btn <- actionButton("prev_btn", "Previous", class = "btn btn-default", width = "100%")
            if (is_first) tagAppendAttributes(btn, disabled = "disabled") else btn
          }),
          column(4),
          column(4, {
            btn <- actionButton("next_btn", "Next", class = "btn btn-default", width = "100%")
            if (is_last) tagAppendAttributes(btn, disabled = "disabled") else btn
          })
        )
      )
    )
  })

  # Download handler
  output$download_csv <- downloadHandler(
    filename = function() {
      paste0(input$rater_id, "_ratings_", Sys.Date(), ".csv")
    },
    content = function(file) {
      req(input$rater_id != "")
      ratings <- rater_ratings()
      if (length(ratings) == 0) {
        write.csv(data.frame(), file, row.names = FALSE)
        return()
      }
      indices <- as.integer(names(ratings))
      df <- data.frame(
        id = problems_df$id[indices],
        set = problems_df$set[indices],
        question_id = problems_df$question_id[indices],
        config = problems_df$config[indices],
        theme = problems_df$theme[indices],
        rating = as.integer(ratings),
        rater_id = input$rater_id,
        stringsAsFactors = FALSE
      )
      write.csv(df, file, row.names = FALSE)
    }
  )
}

shinyApp(ui, server)
